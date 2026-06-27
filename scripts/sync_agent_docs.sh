#!/usr/bin/env bash
# Haelt die agentenspezifischen Root-Configs synchron zu AGENTS.md (Source of Truth).
# CLAUDE.md und GEMINI.md sind abgeleitet: identischer Body, nur die Titelzeile (# NAME.md)
# unterscheidet sich. Codex/Vibe lesen AGENTS.md direkt.
#
# Usage:
#   bash sync_agent_docs.sh          # regeneriert CLAUDE.md + GEMINI.md aus AGENTS.md
#   bash sync_agent_docs.sh --check  # exit 1 wenn out-of-sync, schreibt nichts
#
# Source of Truth ist AGENTS.md. Aenderungen immer dort machen, nie in den Derivaten.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/AGENTS.md"
DERIVED=(CLAUDE GEMINI)

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

if [ ! -f "$SRC" ]; then
  echo "[sync_agent_docs] AGENTS.md fehlt unter $SRC" >&2
  exit 2
fi

# Body = AGENTS.md ab Zeile 2 (Titelzeile wird pro Datei ersetzt).
render() {
  local name="$1"
  printf '# %s.md\n' "$name"
  tail -n +2 "$SRC"
}

rc=0
for name in "${DERIVED[@]}"; do
  target="$REPO/$name.md"
  if [ "$CHECK" -eq 1 ]; then
    if ! diff -q <(render "$name") "$target" >/dev/null 2>&1; then
      echo "[sync_agent_docs] $name.md weicht von AGENTS.md ab — 'bash scripts/sync_agent_docs.sh' ausfuehren." >&2
      rc=1
    fi
  else
    render "$name" > "$target"
    echo "[sync_agent_docs] geschrieben: $name.md"
  fi
done

exit $rc
