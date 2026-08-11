#!/usr/bin/env bash
# Bootstraps tickets/ folder structure in the given directory (default: current dir).
# Idempotent: kann auf bestehende Projekte erneut angewendet werden, um Counter und
# next_ticket_id.sh nachzurüsten, ohne vorhandene Tickets/PROTOCOL.md zu überschreiben.
# For global agent setup (one-time, per machine) use: bash scripts/setup_global_conventions.sh
# Usage: bash scripts/init_tickets.sh [ziel-pfad] [PREFIX]
#   PREFIX (optional): 2-6 Grossbuchstaben. Wird in tickets/PROTOCOL.md als
#   projekt-lokale Laufzeit-Quelle verankert ({PRJ}-Platzhalter wird ersetzt).
#   Fehlt das Argument: bei TTY interaktive Nachfrage, sonst Platzhalter belassen
#   (kein Abbruch). Registry project-identifier.md wird bewusst NICHT angefasst
#   (agent-neutral; siehe IZG-T-045).
TARGET="${1:-.}"

# Projekt-Prefix bestimmen: Argument > interaktiv (nur bei TTY) > leer (Platzhalter).
PRJ="$(printf '%s' "${2:-}" | tr '[:lower:]' '[:upper:]')"
if [ -z "$PRJ" ] && [ -t 0 ]; then
  printf 'Projekt-Prefix (2-6 Grossbuchstaben, Enter = spaeter eintragen): ' > /dev/tty
  read -r _ans < /dev/tty || _ans=""
  PRJ="$(printf '%s' "$_ans" | tr '[:lower:]' '[:upper:]')"
fi
if [ -n "$PRJ" ] && ! printf '%s' "$PRJ" | grep -qE '^[A-Z]{2,6}$'; then
  echo "Warnung: Prefix '$PRJ' ungueltig (erwartet 2-6 Grossbuchstaben). Ignoriert, Platzhalter {PRJ} bleibt." >&2
  PRJ=""
fi

mkdir -p "$TARGET/tickets/open" \
         "$TARGET/tickets/in-progress" \
         "$TARGET/tickets/blocked" \
         "$TARGET/tickets/done"

# Counter nur anlegen wenn fehlend. Startwert 0 genügt — next_ticket_id.sh ist
# selbstheilend und nimmt ohnehin das Maximum aus Counter und realen Tickets.
if [ ! -f "$TARGET/tickets/.counter" ]; then
  echo "0" > "$TARGET/tickets/.counter"
fi

if [ ! -f "$TARGET/tickets/PROTOCOL.md" ]; then
  cat > "$TARGET/tickets/PROTOCOL.md" << 'EOF'
# Tickets

Vollständige Konvention: `tickets.md` im globalen Verzeichnis deines AI-Agenten.

## Tickets finden
Nur auf Ansage. Wenn gesucht wird:
1. `in-progress/` — angefangene Arbeit
2. `open/` — nächste Arbeit
3. `blocked/` — nur wenn Blocker gezielt gelöst werden soll

Nie rekursiv über `tickets/` suchen — `done/` ist Archiv (nach Jahr unterteilt) und
wächst monoton. Immer über die aktiven Ordner oder `scripts/tickets.sh` gehen.

## Dateiname
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Projekt-Prefix aus `doc-ids.md` im globalen Agent-Verzeichnis.

## Ticket-ID vergeben
```bash
bash scripts/next_ticket_id.sh {PRJ}
```

## Statuswechsel
`status:`-Feld im Frontmatter ändern — Hook verschiebt die Datei automatisch.
Verlaufseintrag pflegen: wann, warum, was erledigt/offen.
EOF
fi

# Prefix in PROTOCOL.md verankern: {PRJ}-Platzhalter durch das echte Prefix
# ersetzen. Greift bei frisch erstellter UND bestehender PROTOCOL.md (Nachruesten),
# solange dort noch Platzhalter stehen. PRJ ist auf [A-Z]{2,6} validiert -> sed-sicher.
if [ -n "$PRJ" ] && [ -f "$TARGET/tickets/PROTOCOL.md" ]; then
  sed -i "s/{PRJ}/$PRJ/g" "$TARGET/tickets/PROTOCOL.md"
fi

mkdir -p "$TARGET/scripts"

# REPO_SCRIPTS = das scripts/-Verzeichnis, in dem dieses init_tickets.sh selbst liegt
# (Original im ai-SKILL-set-Repo ODER eine bereits deployte Kopie). Von dort werden
# tickets.sh + next_ticket_id.sh kopiert, wenn vorhanden — nur wenn die Quelle fehlt
# (init_tickets.sh liegt isoliert ohne die Geschwister-Skripte), wird inline
# generiert. Kein Netzwerkzugriff, agent-neutral (IZG-T-083).
REPO_SCRIPTS="$(cd "$(dirname "$0")" && pwd)"

# Kopiert scripts/$1 aus REPO_SCRIPTS nach TARGET/scripts/$1, wenn dort vorhanden
# und nicht bereits dieselbe Datei. Sonst: Fallback-Inhalt (Parameter $2, via stdin
# durch den Aufrufer als Heredoc uebergeben) nur schreiben, falls das Ziel noch fehlt.
deploy_script() {
  local name="$1"
  local src="$REPO_SCRIPTS/$name" dest="$TARGET/scripts/$name"
  if [ -f "$src" ] && ! [ "$src" -ef "$dest" ]; then
    cp "$src" "$dest"
  elif [ ! -f "$dest" ]; then
    cat > "$dest"
  fi
  chmod +x "$dest"
}

# tickets.sh immer (neu) schreiben, damit Bestandsprojekte die aktuelle Logik
# (list/show/next) bekommen.
deploy_script tickets.sh << 'EOF'
#!/usr/bin/env bash
# Schmales Abfrage-Interface fuer tickets/. Ersetzt Glob+Volltext-Read durch
# Frontmatter-Zeilen (list), gezielten Volltext-Read (show) und die bisherige
# next_ticket_id.sh-Logik (next). Siehe IZG-T-083.
# Usage:
#   tickets.sh list [--status open|in-progress|blocked|done] [--group SLUG] [--type TYPE]
#   tickets.sh show <ID>
#   tickets.sh next <PREFIX>
set -euo pipefail

TICKETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/tickets"

# Liest ein Feld aus dem Frontmatter (zwischen den ersten beiden "---"-Zeilen).
frontmatter_field() {
  local file="$1" field="$2"
  awk -v f="$field" '
    /^---$/ { n++; next }
    n == 1 && $0 ~ "^" f ": " { sub("^" f ": ", ""); print; exit }
  ' "$file"
}

cmd_list() {
  local status_filter="" group_filter="" type_filter=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --status) status_filter="$2"; shift 2 ;;
      --group) group_filter="$2"; shift 2 ;;
      --type) type_filter="$2"; shift 2 ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done

  local folders
  if [ -n "$status_filter" ]; then
    folders=("$status_filter")
  else
    folders=(in-progress open blocked)
  fi

  local folder file id type priority slug glob_pattern
  for folder in "${folders[@]}"; do
    [ -d "$TICKETS_DIR/$folder" ] || continue
    # done/ ist nach Jahr unterteilt (IZG-T-084) - eine Ebene tiefer als die
    # aktiven Statusordner.
    if [ "$folder" = "done" ]; then
      glob_pattern="$TICKETS_DIR/$folder"/*/*.md
    else
      glob_pattern="$TICKETS_DIR/$folder"/*.md
    fi
    for file in $glob_pattern; do
      [ -e "$file" ] || continue
      id="$(frontmatter_field "$file" id)"
      [ -n "$id" ] || continue

      type="$(frontmatter_field "$file" type)"
      priority="$(frontmatter_field "$file" priority)"

      if [ -n "$type_filter" ] && [ "$type" != "$type_filter" ]; then
        continue
      fi
      if [ -n "$group_filter" ]; then
        group="$(frontmatter_field "$file" group)"
        [ "$group" = "$group_filter" ] || continue
      fi

      slug="$(basename "$file")"
      slug="${slug#*_}"
      slug="${slug%.md}"

      printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$folder" "$type" "$priority" "$slug"
    done
  done
}

cmd_show() {
  local id="${1:-}"
  if [ -z "$id" ]; then
    echo "Usage: tickets.sh show <ID>" >&2
    exit 1
  fi
  local match
  match="$(grep -rl "^id: ${id}\$" "$TICKETS_DIR" 2>/dev/null | head -1 || true)"
  if [ -z "$match" ]; then
    echo "Ticket nicht gefunden: $id" >&2
    exit 1
  fi
  cat "$match"
}

cmd_next() {
  local PREFIX="${1:-PRJ}"
  local COUNTER_FILE="$TICKETS_DIR/.counter"

  if [ ! -d "$TICKETS_DIR" ]; then
    echo "Fehler: $TICKETS_DIR nicht gefunden. init_tickets.sh ausführen." >&2
    exit 1
  fi

  if command -v flock >/dev/null 2>&1; then
    exec 9>"$COUNTER_FILE.lock"
    flock 9
  fi

  local counter=0 c
  if [ -f "$COUNTER_FILE" ]; then
    c="$(tr -dc '0-9' < "$COUNTER_FILE")"
    [ -n "$c" ] && counter=$((10#$c))
  fi

  local max_existing
  max_existing="$(grep -rhoE "^id: ${PREFIX}-T-[0-9]+" "$TICKETS_DIR" 2>/dev/null \
    | grep -oE '[0-9]+$' | sort -n | tail -1 || true)"
  max_existing=$((10#${max_existing:-0}))

  local floor=$counter
  [ "$max_existing" -gt "$floor" ] && floor=$max_existing

  local next=$((floor + 1))
  echo "$next" > "$COUNTER_FILE"

  printf "%s-T-%03d\n" "$PREFIX" "$next"
}

case "${1:-}" in
  list) shift; cmd_list "$@" ;;
  show) shift; cmd_show "$@" ;;
  next) shift; cmd_next "$@" ;;
  *)
    echo "Usage: tickets.sh {list|show|next} ..." >&2
    exit 1
    ;;
esac
EOF

# next_ticket_id.sh immer (neu) schreiben — bleibt als duenner Wrapper bestehen,
# weil die Konvention (docs/tickets.md, PROTOCOL.md) ihn projektweit referenziert.
deploy_script next_ticket_id.sh << 'EOF'
#!/usr/bin/env bash
# Dünner Wrapper: die Logik lebt in tickets.sh next (IZG-T-083). Bleibt als eigene
# Datei bestehen, weil die Konvention (docs/tickets.md, PROTOCOL.md) sie
# projektweit als ID-Vergabe-Kommando referenziert.
# Usage: bash scripts/next_ticket_id.sh IZG
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/tickets.sh" next "$@"
EOF

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
DEST="$(cd "$TARGET/scripts" && pwd)/init_tickets.sh"
if [ "$SELF" != "$DEST" ]; then
  cp "$0" "$TARGET/scripts/init_tickets.sh"
  chmod +x "$TARGET/scripts/init_tickets.sh"
fi

if [ -n "$PRJ" ]; then
  echo "tickets/ ready in $TARGET (Prefix $PRJ in PROTOCOL.md verankert, scripts deployed)"
else
  echo "tickets/ ready in $TARGET (Prefix nicht gesetzt, Platzhalter {PRJ} bleibt, scripts deployed)"
  echo "Hinweis: Prefix nachtragen via 'bash scripts/init_tickets.sh $TARGET PREFIX' oder {PRJ} in tickets/PROTOCOL.md manuell ersetzen." >&2
fi
