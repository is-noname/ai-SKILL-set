#!/usr/bin/env bash
# Zeigt Ticket-ID + Titel je Status-Ordner (open, in-progress, blocked) an.
# Gedacht fuer eine tmux-Sidebar per `watch -n 5 scripts/ticket_board.sh`.
# Usage: bash scripts/ticket_board.sh [projekt-pfad]
TARGET="${1:-.}"
TICKETS="$TARGET/tickets"

print_section() {
  local label="$1" dir="$2"
  echo "== $label =="
  local found=0
  for f in "$dir"/*.md; do
    [ -f "$f" ] || continue
    local id title
    id="$(grep -m1 '^id:' "$f" | cut -d' ' -f2-)"
    [ -z "$id" ] && continue
    title="$(grep -m1 '^title:' "$f" | cut -d' ' -f2-)"
    printf '%-14s %s\n' "$id" "$title"
    found=1
  done
  [ "$found" -eq 0 ] && echo "(leer)"
  echo
}

print_section "OPEN" "$TICKETS/open"
print_section "IN-PROGRESS" "$TICKETS/in-progress"
print_section "BLOCKED" "$TICKETS/blocked"
