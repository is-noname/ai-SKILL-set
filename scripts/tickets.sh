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
