#!/bin/bash
# GLOBAL: Schutz fuer .env Dateien - API-Keys nicht lesen/editieren/ausgeben
# Deckt zwei Zugriffswege ab: Read/Edit/Write (file_path) und Bash (command) -
# siehe IZG-T-060, `cat .env` etc. lief sonst ungehindert am Read/Edit/Write-Schutz vorbei.
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

if [[ "$FILE_PATH" == *".env"* ]]; then
  deny ".env Dateien duerfen nicht gelesen oder editiert werden (API-Key Schutz)."
fi

if [[ -n "$COMMAND" ]]; then
  # Bekannte Lese-/Ausgabe-/Kopier-Befehle, die .env-Inhalte exponieren koennten.
  READ_CMDS='cat|head|tail|less|more|sed|grep|cp|mv|tac|nl|awk|od|xxd|hexdump|strings|bat|view'
  # Befehl an ;, &&, ||, | in Segmente zerlegen - jedes einzeln pruefen, damit ein
  # unschuldiges Segment (z.B. "echo done") den Deny eines anderen nicht verhindert.
  while IFS= read -r seg; do
    [[ -z "$seg" ]] && continue
    if echo "$seg" | grep -qF '.env' \
      && echo "$seg" | grep -qE "(^|[[:space:]])($READ_CMDS)([[:space:]]|$)"; then
      deny ".env Dateien duerfen nicht per Bash gelesen/kopiert werden (API-Key Schutz)."
    fi
  done < <(echo "$COMMAND" | sed -E 's/(&&|\|\||;|\|)/\n/g')
fi

exit 0
