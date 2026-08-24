#!/usr/bin/env bash
# Interaktiver Ticket-Picker fuer ein tmux-Popup: waehlt ein offenes Ticket per
# fzf und schickt einen Arbeitsauftrag an TARGET_PANE (pane_id, per Env gesetzt,
# vom Aufrufer VOR dem Oeffnen des Popups eingefangen).
# Usage: TARGET_PANE=%3 bash scripts/ticket_picker.sh <projekt-pfad>
set -u
TARGET="${1:-.}"
OPEN_DIR="$TARGET/tickets/open"

[ -n "${TARGET_PANE:-}" ] || { echo "TARGET_PANE nicht gesetzt"; read -r -p "Enter zum Schliessen"; exit 1; }
command -v fzf >/dev/null || { echo "fzf fehlt (sudo apt install fzf)"; read -r -p "Enter zum Schliessen"; exit 1; }
[ -d "$OPEN_DIR" ] || { echo "Kein tickets/open unter $TARGET"; read -r -p "Enter zum Schliessen"; exit 1; }

LINES=""
for f in "$OPEN_DIR"/*.md; do
  [ -f "$f" ] || continue
  id="$(grep -m1 '^id:' "$f" | cut -d' ' -f2-)"
  [ -z "$id" ] && continue
  title="$(grep -m1 '^title:' "$f" | cut -d' ' -f2-)"
  LINES+="${id}"$'\t'"${title}"$'\n'
done

if [ -z "$LINES" ]; then
  echo "Keine offenen Tickets in $OPEN_DIR."
  read -r -p "Enter zum Schliessen"
  exit 0
fi

SELECTED="$(printf '%s' "$LINES" | fzf --delimiter=$'\t' --with-nth=1,2 --prompt="Ticket > ")"
[ -z "$SELECTED" ] && exit 0

ID="$(printf '%s' "$SELECTED" | cut -f1)"
TITLE="$(printf '%s' "$SELECTED" | cut -f2)"

tmux send-keys -t "$TARGET_PANE" -l "arbeite an ${ID}: ${TITLE}"
tmux send-keys -t "$TARGET_PANE" Enter
