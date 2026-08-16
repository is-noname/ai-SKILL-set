#!/bin/bash
# PreToolUse Read: meldet Zweit-Reads derselben, unveraenderten Datei in einer Session.
#
# Hintergrund: Wird dieselbe Datei mehrfach gelesen, steht ihr Inhalt danach mehrfach
# im Kontextfenster und wird in jedem Folge-Turn erneut mitbezahlt. Messung 16.08.2026
# ueber 498 Transcripts: 512 von 3.371 Reads waren Wiederholungen, davon 358 ohne
# Aenderung dazwischen = 277.171 Tokens vermeidbare Kontextlast.
#
# Verhalten:
#   erster Read einer Datei      -> Zustand merken, durchlassen
#   Datei zwischenzeitlich geaendert (mtime oder Groesse abweichend) -> durchlassen
#   unveraendert, erste Wiederholung -> Hinweis via additionalContext (kein deny)
#   unveraendert, weitere Wiederholungen -> still, Hinweis nur einmal je Session/Datei
#   offset oder limit            -> ignoriert, Teil-Reads zaehlen nicht mit
#
# Kein deny: ein Zweit-Read heisst oft, dass der Inhalt aus dem Fenster gefallen ist.
# Hart blocken wuerde zu Ratearbeit statt zu weniger Tokens fuehren.
#
# Zustand: ~/.claude/state/read-dedupe/<session_id>.tsv, Zeilen
#          pfad<TAB>mtime<TAB>groesse<TAB>gemeldet(0|1). Dateien aelter als 7 Tage
#          werden aufgeraeumt (hoechstens einmal taeglich, Marker .last-cleanup).
# Ventil:  READ_DEDUPE_GUARD_OFF=1 schaltet den Hook ab.
# Getrennt von read-size-guard.sh: andere Zustaendigkeit, getrennt abschaltbar.

if [ "$READ_DEDUPE_GUARD_OFF" = "1" ]; then
  exit 0
fi

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')

if [ -z "$FILE" ] || [ ! -f "$FILE" ] || [ -z "$SESSION" ]; then
  exit 0
fi

# Teil-Reads sind bereits begrenzt und markieren keinen Voll-Read als Wiederholung
BOUNDED=$(echo "$INPUT" | jq -r 'if (.tool_input.offset // null) != null or (.tool_input.limit // null) != null then "1" else "0" end')
if [ "$BOUNDED" = "1" ]; then
  exit 0
fi

# Pfade mit Tab oder Zeilenumbruch wuerden das TSV-Format sprengen
case "$FILE" in
  *$'\t'*|*$'\n'*) exit 0 ;;
esac

# Session-ID nur als Dateiname zulassen, kein Pfad-Ausbruch
SESSION_SAFE=$(echo "$SESSION" | tr -c 'A-Za-z0-9._-' '_')

STATE_DIR="${HOME}/.claude/state/read-dedupe"
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
STATE_FILE="${STATE_DIR}/${SESSION_SAFE}.tsv"

# Aufraeumen, hoechstens einmal am Tag: alte Sessions verschwinden nach 7 Tagen
MARKER="${STATE_DIR}/.last-cleanup"
if [ ! -f "$MARKER" ] || [ -n "$(find "$MARKER" -maxdepth 0 -mtime +0 2>/dev/null)" ]; then
  find "$STATE_DIR" -maxdepth 1 -type f -name '*.tsv' -mtime +7 -delete 2>/dev/null
  touch "$MARKER" 2>/dev/null
fi

MTIME=$(stat -c %Y "$FILE" 2>/dev/null || echo 0)
SIZE=$(stat -c %s "$FILE" 2>/dev/null || echo 0)

# Zustand nachschlagen: leer = unbekannt, sonst "mtime groesse gemeldet"
PREV=""
if [ -f "$STATE_FILE" ]; then
  PREV=$(awk -F'\t' -v p="$FILE" '$1 == p { print $2, $3, $4; exit }' "$STATE_FILE")
fi

write_entry() {
  # Zeile fuer $FILE ersetzen bzw. anhaengen, atomar ueber Temp-Datei
  local flag="$1" tmp
  tmp=$(mktemp "${STATE_FILE}.XXXXXX" 2>/dev/null) || return 0
  if [ -f "$STATE_FILE" ]; then
    awk -F'\t' -v p="$FILE" '$1 != p' "$STATE_FILE" > "$tmp" 2>/dev/null
  fi
  printf '%s\t%s\t%s\t%s\n' "$FILE" "$MTIME" "$SIZE" "$flag" >> "$tmp"
  mv "$tmp" "$STATE_FILE" 2>/dev/null || rm -f "$tmp"
}

if [ -z "$PREV" ]; then
  write_entry 0
  exit 0
fi

PREV_MTIME=$(echo "$PREV" | cut -d' ' -f1)
PREV_SIZE=$(echo "$PREV" | cut -d' ' -f2)
PREV_FLAG=$(echo "$PREV" | cut -d' ' -f3)

# Datei hat sich geaendert: der Zweit-Read ist gedeckt, nur Zustand nachziehen.
# Das Melde-Flag bleibt stehen - der Hinweis kommt hoechstens einmal je Datei.
if [ "$PREV_MTIME" != "$MTIME" ] || [ "$PREV_SIZE" != "$SIZE" ]; then
  write_entry "$PREV_FLAG"
  exit 0
fi

if [ "$PREV_FLAG" = "1" ]; then
  exit 0
fi

write_entry 1
jq -n --arg file "$(basename "$FILE")" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ($file + " wurde in dieser Session bereits vollstaendig gelesen und hat sich seitdem nicht geaendert - der Inhalt steht schon im Kontext. Falls nur eine bestimmte Stelle fehlt: Grep mit Pattern oder Read mit offset/limit statt erneutem Voll-Read.")
  }
}'
exit 0
