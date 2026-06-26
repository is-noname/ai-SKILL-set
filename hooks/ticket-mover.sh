#!/bin/bash
# PostToolUse hook: verschiebt Ticket-Dateien wenn status: im Frontmatter vom Ordner abweicht

input=$(cat)

tool_name=$(echo "$input" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$tool_name" == "Edit" || "$tool_name" == "Write" ]] || exit 0

file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -n "$file_path" && -f "$file_path" ]] || exit 0

# Nur Dateien innerhalb eines tickets/-Verzeichnisses
[[ "$file_path" == */tickets/* ]] || exit 0

# Muss gültiges Ticket-Frontmatter haben (id: PRJ-T-NNN)
grep -qE "^id: [A-Z]+-T-[0-9]+" "$file_path" || exit 0

# status:-Feld auslesen
status=$(grep -m1 "^status: " "$file_path" | sed 's/^status: //' | tr -d '[:space:]"'"'")
[[ -n "$status" ]] || exit 0

# Nur bekannte Status-Werte
case "$status" in
  open|in-progress|blocked|done) ;;
  *) exit 0 ;;
esac

current_dir=$(dirname "$file_path")
current_folder=$(basename "$current_dir")

# Nichts zu tun wenn Ordner schon stimmt
[[ "$current_folder" == "$status" ]] && exit 0

tickets_root=$(dirname "$current_dir")
target_dir="$tickets_root/$status"
filename=$(basename "$file_path")

mkdir -p "$target_dir"

# Kollisionsschutz: nie ein vorhandenes Ziel überschreiben (z.B. gleiche ID in
# zwei Ordnern durch manuelles Verschieben). Lieber stehen lassen und warnen.
if [[ -e "$target_dir/$filename" ]]; then
  echo "[ticket-mover] $filename: Ziel $status/ existiert bereits — nicht verschoben (Kollision)" >&2
  exit 0
fi

mv -n "$file_path" "$target_dir/$filename"

echo "[ticket-mover] $filename: $current_folder/ → $status/" >&2
