#!/bin/bash
# GLOBAL: Schutz fuer .env Dateien - API-Keys nicht lesen/editieren/ausgeben
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" == *".env"* ]]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ".env Dateien duerfen nicht gelesen oder editiert werden (API-Key Schutz)."
    }
  }'
  exit 0
fi
exit 0
