#!/usr/bin/env bash
# Drift-Check für global deployte Konventionen/Artefakte (Inverse von
# setup_global.sh). Vergleicht die deployten Dateien in einem Agent-Dir
# gegen die Quelle im Repo und meldet pro Datei: ok / drift / missing.
#
# Read-only — schreibt nie. Zum Re-Deploy: setup_global.sh <agent-dir>.
#
# Usage:
#   bash check_global_drift.sh                # alle bekannten Agent-Dirs unter $HOME
#   bash check_global_drift.sh ~/.claude      # nur ein Agent-Dir
#   bash check_global_drift.sh --all          # explizit alle (wie ohne Arg)
#
# Exit: 0 = alles aktuell, 1 = Drift/Fehlend gefunden, 2 = Aufruf-/Repo-Fehler.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# project-identifier.md ist User-State → NICHT geprüft. Alles hier sind die von
# setup_global.sh stets überschriebenen (= managed) Dateien.
# Format: "<repo-relpath>|<agent-relpath>"
MANAGED=(
  "docs/tickets.md|tickets.md"
  "docs/doc-ids.md|doc-ids.md"
  "scripts/init_tickets.sh|scripts/init_tickets.sh"
  "hooks/ticket-mover.sh|hooks/ticket-mover.sh"
)

KNOWN_AGENT_DIRS=(".claude" ".codex" ".gemini" ".vibe")

# Agent-Dirs bestimmen
agent_dirs=()
if [ "$#" -eq 0 ] || [ "$1" = "--all" ]; then
  for name in "${KNOWN_AGENT_DIRS[@]}"; do
    [ -d "$HOME/$name" ] && agent_dirs+=("$HOME/$name")
  done
  if [ "${#agent_dirs[@]}" -eq 0 ]; then
    echo "Keine bekannten Agent-Dirs unter $HOME gefunden (.claude/.codex/.gemini/.vibe)." >&2
    exit 2
  fi
else
  for arg in "$@"; do
    expanded="$(eval echo "$arg")"
    if [ ! -d "$expanded" ]; then
      echo "Error: $expanded existiert nicht." >&2
      exit 2
    fi
    agent_dirs+=("$expanded")
  done
fi

drift_found=0

for adir in "${agent_dirs[@]}"; do
  echo "== $adir =="
  for entry in "${MANAGED[@]}"; do
    src="$REPO_ROOT/${entry%%|*}"
    dst="$adir/${entry##*|}"
    rel="${entry##*|}"
    if [ ! -f "$src" ]; then
      echo "  ?? $rel — Repo-Quelle fehlt (${entry%%|*})"
      drift_found=1
    elif [ ! -f "$dst" ]; then
      echo "  -- $rel — fehlt (nicht deployt)"
      drift_found=1
    elif diff -q "$src" "$dst" >/dev/null 2>&1; then
      echo "  ok $rel"
    else
      echo "  !! $rel — DRIFT (deployt weicht ab)"
      drift_found=1
    fi
  done
done

if [ "$drift_found" -ne 0 ]; then
  echo
  echo "Drift/Fehlend gefunden. Re-Deploy: bash $REPO_ROOT/scripts/setup_global.sh <agent-dir>"
fi

exit "$drift_found"
