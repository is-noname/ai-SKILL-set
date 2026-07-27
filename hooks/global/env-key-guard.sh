#!/bin/bash
# Blockt Bash-Befehle die API-Keys aus Environment-Variablen auslesen koennten
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Muster die Keys exponieren koennen
if echo "$COMMAND" | grep -qE '^\s*(env|printenv)\s*$'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Nackter env/printenv-Befehl blockiert (API-Key Schutz). Spezifische Var abfragen falls noetig."
    }
  }'
  exit 0
fi

# env mit grep/filter auf Key-Namen - env/printenv muss als eigenstaendiges Token am
# Anfang der Pipe stehen, sonst matcht auch z.B. "find ... -iname *protect-env* | grep -v x"
if echo "$COMMAND" | grep -qE '^\s*(env|printenv)\b.*\|\s*grep' ; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "env-Pipe blockiert (API-Key Schutz)."
    }
  }'
  exit 0
fi

# Direkte Expansion bekannter Key-Variablen
if echo "$COMMAND" | grep -qE '\$(ANTHROPIC|OPENAI|GEMINI|CLAUDE|API_KEY|SECRET|TOKEN|PASSWORD)[_A-Z]*'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Direkte Key-Variable blockiert (API-Key Schutz)."
    }
  }'
  exit 0
fi

exit 0
