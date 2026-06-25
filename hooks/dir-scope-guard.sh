#!/bin/bash
# Blockt Read/Write/Edit auf sensible Verzeichnisse gemaess dir-scope.conf
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# Kein Dateipfad im Input -> kein Check noetig
[[ -z "$FILE_PATH" ]] && exit 0

# Konfiguration laden
CONF="$HOME/.claude/hooks/dir-scope.conf"
[[ ! -f "$CONF" ]] && exit 0
source "$CONF"

# Pfad normalisieren (~ aufloesen falls vorhanden)
REAL_PATH=$(realpath -m "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")

for BLOCKED in "${BLOCKED_DIRS[@]}"; do
  REAL_BLOCKED=$(realpath -m "$BLOCKED" 2>/dev/null || echo "$BLOCKED")
  if [[ "$REAL_PATH" == "$REAL_BLOCKED"* ]]; then
    jq -n --arg path "$FILE_PATH" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: ("Zugriff auf sensibles Verzeichnis blockiert: " + $path + ". Eintrag in ~/.claude/hooks/dir-scope.conf anpassen falls beabsichtigt.")
      }
    }'
    exit 0
  fi
done

exit 0
