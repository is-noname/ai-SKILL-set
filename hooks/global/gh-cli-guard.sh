#!/bin/bash
# Blockt gefaehrliche GitHub CLI Operationen
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Repo-Visibility aendern auf public: hart blocken
if echo "$COMMAND" | grep -qE 'gh\s+repo\s+edit.*--visibility[= ]+public'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Repo auf public stellen blockiert."
    }
  }'
  exit 0
fi

# Repo-Visibility aendern auf private: nur mit expliziter User-Bestaetigung
if echo "$COMMAND" | grep -qE 'gh\s+repo\s+edit.*--visibility[= ]+private'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask"
    },
    systemMessage: "Repo-Visibility -> private erkannt — nur ausfuehren wenn der User es explizit angefragt hat."
  }'
  exit 0
fi

# Repo erstellen (public)
if echo "$COMMAND" | grep -qE 'gh\s+repo\s+create.*--public'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Public Repo erstellen blockiert."
    }
  }'
  exit 0
fi

# PR/Issue erstellen
if echo "$COMMAND" | grep -qE 'gh\s+(pr|issue)\s+create'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "PR/Issue erstellen ohne explizite Anfrage blockiert."
    }
  }'
  exit 0
fi

# Repo/Branch loeschen
if echo "$COMMAND" | grep -qE 'gh\s+(repo\s+delete|api.*DELETE)'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Loeschen via gh blockiert."
    }
  }'
  exit 0
fi
exit 0
