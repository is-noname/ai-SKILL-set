#!/bin/bash
# post_tool Hook fuer Vibe (IZG-T-088): duenner Adapter um tickets.sh sync,
# analog zu ticket-mover.sh (Claude). Vibe reicht den Payload als JSON auf
# stdin (PostToolInvocation, vibe/core/hooks/models.py) — Feldnamen dort sind
# snake_case (tool_name, tool_input), kein Alias-Mapping.
#
# Kein match-Filter in hooks.toml auf tool_name: welche Namen Vibe fuer
# Edit/Write intern vergibt, ist ueber die installierte Version nicht sicher
# greifbar. Stattdessen filtert dieses Skript selbst ueber tool_input.file_path
# — robuster als eine geratene Namensliste, und tickets.sh sync ist billig
# genug (ein Frontmatter-grep), um auch bei einem Treffer auf einem
# Nicht-Ticket-Tool-Call keine spuerbare Kosten zu verursachen.

input=$(cat)

file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -n "$file_path" && -f "$file_path" && "$file_path" == */tickets/* ]] || exit 0

tickets_root="${file_path%%/tickets/*}"
tickets_sh="$tickets_root/scripts/tickets.sh"
[[ -x "$tickets_sh" ]] || exit 0

msg="$("$tickets_sh" sync "$file_path" 2>&1)"
[[ -n "$msg" ]] || exit 0

echo "[ticket-mover] $msg" >&2
jq -n --arg m "[ticket-mover] $msg" '{hook_specific_output: {additional_context: $m}}'
