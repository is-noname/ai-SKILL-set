#!/bin/bash
# PreToolUse-Hook (Bash): aktualisiert das Kopf-Inhaltsverzeichnis (Funktionsname +
# Zeilennummer) fuer geskriptete Dateien vor git commit, wenn eine der ueberwachten
# Dateien gestaged ist. Schlaegt update_script_toc.py fehl, wird der Commit
# abgebrochen (exit 2) und die Fehlerausgabe sichtbar gemacht.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit'; then
  # Repo aus dem aktuellen Verzeichnis ableiten, per AI_SKILL_SET_REPO ueberschreibbar.
  # Der Hook ist global registriert und laeuft daher auch in fremden Repos - der
  # Marker-Check darunter sorgt dafuer, dass er dort wirkungslos bleibt.
  REPO="${AI_SKILL_SET_REPO:-$(git rev-parse --show-toplevel 2>/dev/null)}"
  [ -n "$REPO" ] || exit 0
  [ -f "$REPO/scripts/update_script_toc.py" ] || exit 0

  TOC_FILES="scripts/setup_global_conventions.sh scripts/tickets.sh"
  STAGED=""
  for f in $TOC_FILES; do
    if git -C "$REPO" diff --cached --name-only | grep -qx "$f"; then
      STAGED="$STAGED $REPO/$f"
    fi
  done

  if [ -n "$STAGED" ]; then
    OUT="$(python3 "$REPO/scripts/update_script_toc.py" $STAGED 2>&1)"
    RC=$?
    if [ "$RC" -ne 0 ]; then
      echo "[pre-commit-toc] update_script_toc.py fehlgeschlagen (exit $RC) — Commit abgebrochen." >&2
      echo "$OUT" >&2
      exit 2
    fi
    git -C "$REPO" add $STAGED 2>/dev/null
  fi
fi

exit 0
