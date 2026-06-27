#!/bin/bash
# Blockt git commit ohne explizite User-Anfrage
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask"
    },
    systemMessage: "Git-Commit erkannt — nur committen wenn der User es explizit angefragt hat."
  }'
  exit 0
fi
exit 0
