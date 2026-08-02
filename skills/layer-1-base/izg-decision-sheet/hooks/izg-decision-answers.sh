#!/bin/bash
# UserPromptSubmit hook: holt exportierte Decision-Sheet-Antworten ab.
#
# Trigger: der Marker "#answers" irgendwo im Prompt (optional mit Slug:
# "#answers ticketsystem-v2"). Ohne Marker macht der Hook nichts.
#
# Die eigentliche Arbeit - Download-Ordner durchsuchen, Datei nach
# <projekt>/.decisions/ verschieben, Inhalt ausgeben - steckt in fetch_answers.py.
# Dieser Hook ist nur der Trigger: stdout eines UserPromptSubmit-Hooks landet im
# Kontext des Agenten. Auf Systemen ohne Hooks ruft der Agent dasselbe Script
# direkt auf, damit die Logik nur einmal existiert.
#
# Gehoert zum Skill skills/layer-1-base/izg-decision-sheet (siehe dessen SKILL.md).

input=$(cat)

prompt=$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)
[[ "$prompt" == *"#answers"* ]] || exit 0

project=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
[[ -n "$CLAUDE_PROJECT_DIR" ]] && project="$CLAUDE_PROJECT_DIR"
[[ -n "$project" && -d "$project" ]] || project="$PWD"

fetcher="$HOME/ai-shared/izg-decision-sheet/fetch_answers.py"
if [[ ! -f "$fetcher" ]]; then
  echo "izg-decision-sheet: $fetcher fehlt - globales Setup nicht gelaufen."
  echo "Fix: bash <ai-SKILL-set>/scripts/setup_global_conventions.sh ~/.claude"
  exit 0
fi

# Optionaler Slug direkt hinter dem Marker: "#answers mein-sheet"
slug=$(printf '%s' "$prompt" | sed -n 's/.*#answers[[:space:]]\{1,\}\([A-Za-z0-9._-]\{1,\}\).*/\1/p' | head -1)

python3 "$fetcher" --project "$project" ${slug:+--slug "$slug"} 2>&1
exit 0
