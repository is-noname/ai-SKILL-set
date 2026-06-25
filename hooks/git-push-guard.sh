#!/bin/bash
# Blockt git push (besonders --force)
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+push.*--force'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny"
    },
    systemMessage: "Force-Push ist VERBOTEN."
  }'
  exit 0
fi

if echo "$COMMAND" | grep -qE 'git\s+push'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask"
    },
    systemMessage: "Git-Push erkannt — nur pushen wenn der User es explizit angefragt hat."
  }'
  exit 0
fi
exit 0
