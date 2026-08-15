#!/usr/bin/env bash
# Variante "ohne-skill": der Skill liegt nicht in der Agent-Konfiguration.
# Laeuft im Messprojekt (bench.py setzt cwd).
set -euo pipefail

here="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

rm -rf .claude/skills/izg-decision-sheet
rm -rf .decisions
cp "$here/projekt/CONTEXT.md" ./CONTEXT.md
