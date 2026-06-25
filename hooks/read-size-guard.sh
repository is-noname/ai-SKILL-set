#!/bin/bash
# PreToolUse Read: Warnt bei grossen Dateien (>1000 Zeilen)
# Blockt .jsonl/.log Dateien (Transcripts etc.)
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  exit 0
fi

# .jsonl und .log Dateien hart blockieren (Transcripts, Logs)
if echo "$FILE" | grep -qE '\.(jsonl|log)$'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Datei-Typ .jsonl/.log blockiert (zu gross, meist Transcripts). Nutze Grep mit spezifischem Pattern statt Read."
    }
  }'
  exit 0
fi

# Groesse pruefen (nur regulaere Dateien)
LINES=$(wc -l < "$FILE" 2>/dev/null || echo 0)

if [ "$LINES" -gt 1000 ]; then
  # Nicht blockieren, nur warnen + Hinweis
  jq -n --arg lines "$LINES" --arg file "$(basename "$FILE")" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: ("ACHTUNG: " + $file + " hat " + $lines + " Zeilen. Nutze offset/limit Parameter um nur den relevanten Abschnitt zu lesen.")
    }
  }'
fi

exit 0
