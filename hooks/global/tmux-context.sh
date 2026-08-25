#!/bin/bash
# GLOBAL: Meldet beim SessionStart, ob eine tmux-Session laeuft und welche Panes frei sind
# (pane_current_command in bash|zsh|sh|fish - dieselbe Pruefung wie tmuxx.sh start --pane).
# Erspart den sonst noetigen `tmux list-panes`-Orientierungs-Turn vor Worker-Start (IZG-T-168).
set -euo pipefail

if [ -z "${TMUX:-}" ]; then
  jq -n '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: "tmux: nein"}}'
  exit 0
fi

cur=$(tmux display-message -p '#{session_name}:#{window_index}.#{pane_index} #{pane_id}' 2>/dev/null) || {
  jq -n '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: "tmux: nein"}}'
  exit 0
}

panes=$(tmux list-panes -F '#{pane_id} #{pane_current_command}' 2>/dev/null) || panes=""
total=$(printf '%s\n' "$panes" | grep -c . || true)

free=""
while IFS=' ' read -r pid cmd; do
  [ -z "$pid" ] && continue
  case "$cmd" in
    bash|zsh|sh|fish) free="$free $pid" ;;
  esac
done <<< "$panes"
free="${free# }"
[ -n "$free" ] || free="keine"

msg="tmux: $cur, $total Panes (frei: $free)"

cheatsheet="$HOME/ai-shared/tmuxxing-cheatsheet.md"
if [ -f "$cheatsheet" ]; then
  content=$(cat "$cheatsheet") || content=""
  if [ -n "$content" ]; then
    msg="$msg

$content"
  fi
fi

jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $m}}'
