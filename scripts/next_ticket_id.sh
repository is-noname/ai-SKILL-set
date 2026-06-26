#!/usr/bin/env bash
# Gibt die nächste Ticket-ID aus und aktualisiert den Zähler.
# Selbstheilend: nimmt das Maximum aus dem Zähler UND den bereits existierenden
# Tickets dieses Präfixes (über alle Status-Ordner). Damit gibt es genau eine
# Quelle der Wahrheit — egal ob der Counter fehlt, driftet oder das Projekt
# nachträglich gebootstrappt wurde.
# Usage: bash scripts/next_ticket_id.sh IZG
set -euo pipefail
PREFIX="${1:-PRJ}"
TICKETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/tickets"
COUNTER_FILE="$TICKETS_DIR/.counter"

if [ ! -d "$TICKETS_DIR" ]; then
  echo "Fehler: $TICKETS_DIR nicht gefunden. init_tickets.sh ausführen." >&2
  exit 1
fi

# Zählerwert (0 wenn Datei fehlt oder nicht-numerisch)
counter=0
if [ -f "$COUNTER_FILE" ]; then
  c="$(tr -dc '0-9' < "$COUNTER_FILE")"
  [ -n "$c" ] && counter=$((10#$c))
fi

# Höchste bereits vergebene Nummer für dieses Präfix über alle Ordner
max_existing="$(grep -rhoE "^id: ${PREFIX}-T-[0-9]+" "$TICKETS_DIR" 2>/dev/null \
  | grep -oE '[0-9]+$' | sort -n | tail -1)"
max_existing=$((10#${max_existing:-0}))

floor=$counter
[ "$max_existing" -gt "$floor" ] && floor=$max_existing

next=$((floor + 1))
echo "$next" > "$COUNTER_FILE"

printf "%s-T-%03d\n" "$PREFIX" "$next"
