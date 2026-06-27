#!/bin/bash
# Blockt destruktive Git-Operationen
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+(reset\s+--hard|clean\s+-f|checkout\s+\.|branch\s+-D|rebase\s+-i)'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Destruktive Git-Operation blockiert. Bitte User fragen."
    }
  }'
  exit 0
fi
exit 0
