#!/usr/bin/env bash
# Variante "mit-skill": Skill projektlokal einspielen und modellaufrufbar machen.
#
# Im Repo steht `disable-model-invocation: true` - der Skill wird sonst nur per
# Slash-Command geladen. Die Testaufgabe ist fuer beide Varianten identisch und
# nennt keinen Skill, also muss das Modell ihn selbst ziehen duerfen.
set -euo pipefail

here="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
skills="$(cd "$here/../../../../.." && pwd)"  # benchmark/<task>/ -> izg-benchmark-actions -> coding -> layer-3-domain -> skills/
src="$skills/layer-1-base/izg-decision-sheet"
dst=".claude/skills/izg-decision-sheet"

rm -rf .decisions
cp "$here/projekt/CONTEXT.md" ./CONTEXT.md

rm -rf "$dst"
mkdir -p "$dst"
cp "$src/SKILL.md" "$dst/"
cp -r "$src/assets" "$src/scripts" "$dst/"
sed -i '/^disable-model-invocation:/d' "$dst/SKILL.md"
