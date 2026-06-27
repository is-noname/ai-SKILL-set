#!/bin/bash
# PreToolUse-Hook (Bash): regeneriert registry.json vor git commit wenn SKILL.md-Dateien
# gestagt sind. Schlägt die Validierung fehl, wird der Commit abgebrochen (exit 2) und die
# Fehlerausgabe sichtbar gemacht — eine invalide Registry darf nicht committet werden.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit'; then
  REPO="$(git -C /home/izg/Dokumente/AI/ai-SKILL-set rev-parse --show-toplevel 2>/dev/null || echo /home/izg/Dokumente/AI/ai-SKILL-set)"
  if git -C "$REPO" diff --cached --name-only | grep -q 'SKILL\.md'; then
    OUT="$(python3 "$REPO/scripts/generate_registry.py" 2>&1)"
    RC=$?
    if [ "$RC" -ne 0 ]; then
      echo "[pre-commit-registry] generate_registry.py fehlgeschlagen (exit $RC) — Commit abgebrochen." >&2
      echo "$OUT" >&2
      exit 2
    fi
    git -C "$REPO" add "$REPO/registry.json" 2>/dev/null
  fi
fi

exit 0
