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

# REPO_SCRIPTS = das scripts/-Verzeichnis, in dem dieses init_tickets.sh selbst liegt
# (Original im ai-SKILL-set-Repo ODER eine bereits deployte Kopie). Wird hier schon
# gebraucht, um die PROTOCOL.md-Vorlage zu finden (siehe unten) und weiter unten
# erneut fuer deploy_script.
REPO_SCRIPTS="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$TARGET/tickets/PROTOCOL.md" ]; then
  TEMPLATE="$REPO_SCRIPTS/ticket_protocol_template.md"
  if [ ! -f "$TEMPLATE" ]; then
    echo "Fehler: $TEMPLATE nicht gefunden. init_tickets.sh muss zusammen mit den" >&2
    echo "Geschwisterskripten aus scripts/ aufgerufen werden (isolierter Aufruf" >&2
    echo "wird nicht unterstuetzt) — siehe scripts/tickets.sh im ai-SKILL-set-Repo." >&2
    exit 1
  fi
  cp "$TEMPLATE" "$TARGET/tickets/PROTOCOL.md"
fi

# Prefix in PROTOCOL.md verankern: {PRJ}-Platzhalter durch das echte Prefix
# ersetzen. Greift bei frisch erstellter UND bestehender PROTOCOL.md (Nachruesten),
# solange dort noch Platzhalter stehen. PRJ ist auf [A-Z]{2,6} validiert -> sed-sicher.
if [ -n "$PRJ" ] && [ -f "$TARGET/tickets/PROTOCOL.md" ]; then
  sed -i "s/{PRJ}/$PRJ/g" "$TARGET/tickets/PROTOCOL.md"
fi

mkdir -p "$TARGET/scripts"

# Von REPO_SCRIPTS (oben ermittelt) werden tickets.sh + next_ticket_id.sh kopiert.
# Kein Netzwerkzugriff, agent-neutral (IZG-T-083). Isolierter Aufruf ohne
# Geschwisterskripte wird nicht unterstuetzt (IZG-T-089) — deploy_script bricht
# dann mit klarer Fehlermeldung ab.

# Kopiert scripts/$1 aus REPO_SCRIPTS nach TARGET/scripts/$1 (immer neu, damit
# Bestandsprojekte die aktuelle Logik bekommen). Bricht ab, wenn die Quelle fehlt
# (init_tickets.sh liegt isoliert ohne die Geschwister-Skripte) statt sie inline
# zu duplizieren — einzige Quelle bleibt scripts/tickets.sh im Repo (IZG-T-089).
deploy_script() {
  local name="$1"
  local src="$REPO_SCRIPTS/$name" dest="$TARGET/scripts/$name"
  if [ ! -f "$src" ]; then
    echo "Fehler: $src nicht gefunden. init_tickets.sh muss zusammen mit den" >&2
    echo "Geschwisterskripten aus scripts/ aufgerufen werden (isolierter Aufruf" >&2
    echo "wird nicht unterstuetzt) — siehe scripts/tickets.sh im ai-SKILL-set-Repo." >&2
    exit 1
  fi
  if ! [ "$src" -ef "$dest" ]; then
    cp "$src" "$dest"
  fi
  chmod +x "$dest"
}

deploy_script tickets.sh
deploy_script next_ticket_id.sh

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
