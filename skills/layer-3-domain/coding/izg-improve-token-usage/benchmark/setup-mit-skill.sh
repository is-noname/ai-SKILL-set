#!/usr/bin/env bash
# Variante "mit-skill": Skill projektlokal einspielen und modellaufrufbar machen.
#
# Im Repo steht `disable-model-invocation: true` — der Skill wird sonst nur per
# Slash-Command geladen. Die Testaufgabe ist fuer beide Varianten identisch und
# nennt keinen Skill, also muss das Modell ihn selbst ziehen duerfen.
set -euo pipefail

src="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.."
dst=".claude/skills/izg-improve-token-usage"

rm -rf "$dst"
mkdir -p "$dst"
cp -r "$src/SKILL.md" "$src/HTML-REPORT.md" "$src/scripts" "$dst/"
sed -i '/^disable-model-invocation:/d' "$dst/SKILL.md"
