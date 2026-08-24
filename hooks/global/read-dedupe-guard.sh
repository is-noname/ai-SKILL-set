#!/bin/bash
# PreToolUse Read: blockt Wieder-Reads derselben, unveraenderten Datei in einer Session.
#
# Hintergrund: Wird dieselbe Datei mehrfach gelesen, steht ihr Inhalt danach mehrfach
# im Kontextfenster und wird in jedem Folge-Turn erneut mitbezahlt. Messung 16.08.2026
# ueber 498 Transcripts: 512 von 3.371 Reads waren Wiederholungen, davon 358 ohne
# Aenderung dazwischen = 277.171 Tokens vermeidbare Kontextlast.
#
# Verhalten:
#   erster Voll-Read einer Datei -> Zustand merken, durchlassen
#   Teil-Read ohne vorherigen Voll-Read -> durchlassen, nicht gemerkt (Weiterblaettern)
#   Datei zwischenzeitlich geaendert (mtime oder Groesse abweichend) -> durchlassen
#   unveraendert, innerhalb des Fensters -> deny mit Zeitpunkt des ersten Reads
#   unveraendert, ausserhalb des Fensters -> Hinweis via additionalContext, einmalig
#
# Fenster: WINDOW_LINES neue Transcript-Zeilen seit dem gemerkten Read. Hergeleitet aus
# 46 Wieder-Reads unveraenderter Dateien ueber 35 Projekte (Messung 22.08.2026): der
# Zeilenabstand deckt bei 200 Zeilen 89 % der Faelle ab (Median 39, p95 229), das
# entspricht rund 30 Agent-Turns. Jenseits davon ist ein Kontextverlust plausibel und
# ein Block wuerde zu Ratearbeit fuehren, deshalb dort nur der Hinweis.
# Ohne lesbares Transcript wird nicht geblockt - lieber ein Read zu viel als ein
# Fehlblock ohne Datengrundlage.
#
# Teil-Reads: werden geblockt, wenn ein Voll-Read derselben unveraenderten Datei im
# Fenster liegt (der Inhalt steht dann komplett im Kontext). Ohne vorherigen Voll-Read
# bleiben sie unangetastet - aufeinanderfolgende offset/limit-Reads sind meist
# disjunktes Weiterblaettern, kein Duplikat.
#
# Zustand: ~/.claude/state/read-dedupe/<session_id>.tsv, Zeilen
#          pfad<TAB>mtime<TAB>groesse<TAB>gemeldet(0|1)<TAB>transcript_zeilen<TAB>zeitpunkt
#          Dateien aelter als 7 Tage werden aufgeraeumt (hoechstens einmal taeglich,
#          Marker .last-cleanup).
# Ventil:  READ_DEDUPE_GUARD_OFF=1 schaltet den Hook ab.
#          READ_DEDUPE_GUARD_WINDOW=<n> setzt das Fenster in Transcript-Zeilen,
#          0 = nie blocken (nur Hinweis wie vor dem 22.08.2026).
# Getrennt von read-size-guard.sh: andere Zustaendigkeit, getrennt abschaltbar.

if [ "$READ_DEDUPE_GUARD_OFF" = "1" ]; then
  exit 0
fi

WINDOW_LINES=${READ_DEDUPE_GUARD_WINDOW:-200}
case "$WINDOW_LINES" in
  ''|*[!0-9]*) WINDOW_LINES=200 ;;
esac

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')

if [ -z "$FILE" ] || [ ! -f "$FILE" ] || [ -z "$SESSION" ]; then
  exit 0
fi

BOUNDED=$(echo "$INPUT" | jq -r 'if (.tool_input.offset // null) != null or (.tool_input.limit // null) != null then "1" else "0" end')

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

# Fortschrittsmass der Session. -1 = unbekannt, dann wird nicht geblockt.
LINES=-1
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  LINES=$(wc -l < "$TRANSCRIPT" 2>/dev/null | tr -d ' ')
  case "$LINES" in
    ''|*[!0-9]*) LINES=-1 ;;
  esac
fi
NOW=$(date '+%H:%M:%S')

# Zustand nachschlagen: leer = unbekannt, sonst "mtime groesse gemeldet zeilen zeitpunkt"
PREV=""
if [ -f "$STATE_FILE" ]; then
  PREV=$(awk -F'\t' -v p="$FILE" '$1 == p { print $2, $3, $4, $5, $6; exit }' "$STATE_FILE")
fi

write_entry() {
  # Zeile fuer $FILE ersetzen bzw. anhaengen, atomar ueber Temp-Datei
  local flag="$1" lines="$2" ts="$3" tmp
  tmp=$(mktemp "${STATE_FILE}.XXXXXX" 2>/dev/null) || return 0
  if [ -f "$STATE_FILE" ]; then
    awk -F'\t' -v p="$FILE" '$1 != p' "$STATE_FILE" > "$tmp" 2>/dev/null
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$FILE" "$MTIME" "$SIZE" "$flag" "$lines" "$ts" >> "$tmp"
  mv "$tmp" "$STATE_FILE" 2>/dev/null || rm -f "$tmp"
}

if [ -z "$PREV" ]; then
  # Nur Voll-Reads werden gemerkt - ein Teil-Read deckt den Rest der Datei nicht ab.
  [ "$BOUNDED" = "0" ] && write_entry 0 "$LINES" "$NOW"
  exit 0
fi

PREV_MTIME=$(echo "$PREV" | cut -d' ' -f1)
PREV_SIZE=$(echo "$PREV" | cut -d' ' -f2)
PREV_FLAG=$(echo "$PREV" | cut -d' ' -f3)
PREV_LINES=$(echo "$PREV" | cut -d' ' -f4)
PREV_TS=$(echo "$PREV" | cut -d' ' -f5)
case "$PREV_LINES" in
  ''|*[!0-9]*) PREV_LINES=-1 ;;
esac
[ -z "$PREV_TS" ] && PREV_TS="frueher in dieser Session"

# Datei hat sich geaendert: der Wieder-Read ist gedeckt, nur Zustand nachziehen.
# Das Melde-Flag bleibt stehen - der Hinweis kommt hoechstens einmal je Datei.
if [ "$PREV_MTIME" != "$MTIME" ] || [ "$PREV_SIZE" != "$SIZE" ]; then
  if [ "$BOUNDED" = "0" ]; then
    write_entry "$PREV_FLAG" "$LINES" "$NOW"
  else
    # Teil-Read einer geaenderten Datei: der gemerkte Voll-Read ist entwertet.
    write_entry "$PREV_FLAG" -1 "$PREV_TS"
  fi
  exit 0
fi

# Innerhalb des Fensters blocken. Fenster 0 oder unbekannter Fortschritt -> nur Hinweis.
if [ "$WINDOW_LINES" -gt 0 ] && [ "$LINES" -ge 0 ] && [ "$PREV_LINES" -ge 0 ] \
   && [ $((LINES - PREV_LINES)) -lt "$WINDOW_LINES" ]; then
  jq -n --arg file "$(basename "$FILE")" --arg ts "$PREV_TS" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ($file + " wurde in dieser Session um " + $ts + " bereits vollstaendig gelesen und hat sich seitdem nicht geaendert - der Inhalt steht noch im Kontextfenster, scrolle dort zurueck statt erneut zu lesen. Falls wirklich etwas fehlt: Grep mit Pattern auf die gesuchte Stelle. Ventil, wenn der Read wirklich noetig ist: READ_DEDUPE_GUARD_OFF=1.")
    }
  }'
  exit 0
fi

if [ "$PREV_FLAG" = "1" ]; then
  exit 0
fi

write_entry 1 "$LINES" "$NOW"
jq -n --arg file "$(basename "$FILE")" --arg ts "$PREV_TS" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ($file + " wurde in dieser Session um " + $ts + " bereits vollstaendig gelesen und hat sich seitdem nicht geaendert. Der Read laeuft durch, weil der Inhalt inzwischen aus dem Fenster gefallen sein kann. Falls nur eine bestimmte Stelle fehlt: Grep mit Pattern oder Read mit offset/limit statt erneutem Voll-Read.")
  }
}'
exit 0
