#!/bin/bash
# Regeneriert registry.json vor git commit wenn SKILL.md Dateien gestagt sind.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit'; then
  REPO="$(git -C /home/izg/Dokumente/AI/ai-SKILL-set rev-parse --show-toplevel 2>/dev/null || echo /home/izg/Dokumente/AI/ai-SKILL-set)"
  if git -C "$REPO" diff --cached --name-only | grep -q 'SKILL\.md'; then
    python3 "$REPO/scripts/generate_registry.py" >/dev/null 2>&1
    git -C "$REPO" add "$REPO/registry.json" 2>/dev/null
  fi
fi

exit 0
