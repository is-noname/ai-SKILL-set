#!/bin/bash
# PreToolUse-Hook (Bash): haelt CLAUDE.md/GEMINI.md synchron zu AGENTS.md vor git commit.
# Ist eine der drei Root-Configs gestagt, werden die Derivate aus AGENTS.md regeneriert und
# nachgestagt. Driftet etwas, das sich nicht regenerieren laesst, bricht der Commit ab (exit 2).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit'; then
  REPO="$(git -C /home/izg/Dokumente/AI/ai-SKILL-set rev-parse --show-toplevel 2>/dev/null || echo /home/izg/Dokumente/AI/ai-SKILL-set)"
  if git -C "$REPO" diff --cached --name-only | grep -qE '^(AGENTS|CLAUDE|GEMINI)\.md$'; then
    OUT="$(bash "$REPO/scripts/sync_agent_docs.sh" 2>&1)"
    RC=$?
    if [ "$RC" -ne 0 ]; then
      echo "[pre-commit-agentdocs] sync_agent_docs.sh fehlgeschlagen (exit $RC) — Commit abgebrochen." >&2
      echo "$OUT" >&2
      exit 2
    fi
    git -C "$REPO" add "$REPO/CLAUDE.md" "$REPO/GEMINI.md" 2>/dev/null
  fi
fi

exit 0
