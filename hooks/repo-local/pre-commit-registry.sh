#!/bin/bash
# PreToolUse-Hook (Bash): regeneriert registry.json vor git commit wenn SKILL.md-Dateien
# gestagt sind. Schlägt die Validierung fehl, wird der Commit abgebrochen (exit 2) und die
# Fehlerausgabe sichtbar gemacht — eine invalide Registry darf nicht committet werden.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit'; then
  # Repo aus dem aktuellen Verzeichnis ableiten, per AI_SKILL_SET_REPO ueberschreibbar.
  # Der Hook ist global registriert und laeuft daher auch in fremden Repos - der
  # Marker-Check darunter sorgt dafuer, dass er dort wirkungslos bleibt.
  REPO="${AI_SKILL_SET_REPO:-$(git rev-parse --show-toplevel 2>/dev/null)}"
  [ -n "$REPO" ] || exit 0
  [ -f "$REPO/scripts/generate_registry.py" ] || exit 0
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
