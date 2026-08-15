#!/usr/bin/env bash
# Legt das Messprojekt an, bevor der erste Lauf startet.
#
# Warum ausserhalb des Repos: `claude` laedt jede CLAUDE.md oberhalb des
# Arbeitsverzeichnisses. Laege das Fixture unter skills/, wuerde die CLAUDE.md
# von ai-SKILL-set ("Stop. Read this before scanning the repo.") in jedem Lauf
# mitgemessen und den Lauf in eine Rueckfrage kippen - fuer beide Varianten
# gleich, aber die Messung waere wertlos.
set -euo pipefail

here="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
dst="${IZG_BENCH_PROJEKT:-$HOME/.local/share/izg-bench/projekte/notizbox}"

mkdir -p "$dst"
cp "$here/projekt/CONTEXT.md" "$dst/"
cp "$here/projekt/.gitignore" "$dst/"

echo "Messprojekt: $dst"
