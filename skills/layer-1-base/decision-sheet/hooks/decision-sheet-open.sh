#!/bin/bash
# Stop hook: oeffnet ein neu geschriebenes Decision Sheet, sobald der Agent fertig ist.
#
# Bewusst als Stop-Hook und nicht als PostToolUse: so ist es egal, WIE das Sheet
# entstanden ist (Write, Edit, Bash-Heredoc, Script) - der Hook fragt nur, ob eins
# auf den User wartet. Und er feuert erst, wenn der Agent zu Ende geredet hat, statt
# mitten im Turn ein Fenster aufzureissen.
#
# Der Hook ist nur der Trigger. Was "wartet auf den User" heisst - Stempel,
# mtime-Aufloesung, Antwort-ist-neuer, Sortierung - steht in sheet_state.py, damit es
# testbar und auch fuer Codex/Vibe/Gemini erreichbar ist.
#
# Gegenstueck: decision-answers.sh holt die Antworten zurueck (#answers).
# Gehoert zum Skill skills/layer-1-base/decision-sheet.

input=$(cat)

project=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
[[ -n "$CLAUDE_PROJECT_DIR" ]] && project="$CLAUDE_PROJECT_DIR"
[[ -n "$project" && -d "$project" ]] || project="$PWD"

shared="$HOME/ai-shared/decision-sheet"
[[ -f "$shared/render_sheet.py" && -f "$shared/sheet_state.py" ]] || exit 0

sheet=$(python3 "$shared/sheet_state.py" pending "$project" 2>/dev/null) || exit 0
[[ -n "$sheet" ]] || exit 0
slug=$(basename "$sheet" .jsonl)

# --force-open: das Script erkennt sonst diesen Hook in der settings.json und
# ueberliesse ihm das Oeffnen - also sich selbst. Dann ginge nie ein Fenster auf.
render_out=$(python3 "$shared/render_sheet.py" "$sheet" --force-open 2>&1)
render_rc=$?

# Beim Oeffnen stempelt das Script selbst; hier steht es noch einmal fuer den
# Fehlerfall, in dem es vorher abbricht - sonst wiederholt ein defektes Sheet seine
# Meldung in jedem Turn. Wird es korrigiert, aendert sich die mtime und es kommt
# erneut dran. Zweimal stempeln schadet nicht, der Eintrag ist derselbe.
python3 "$shared/sheet_state.py" mark-opened "$sheet" 2>/dev/null

if [[ $render_rc -eq 0 ]]; then
  echo "Decision Sheet geoeffnet: $slug ($(grep -c . "$sheet") Zeilen)"
else
  # Sheet ist defekt - Validator-Meldung durchreichen, damit sie im Transkript steht.
  echo "Decision Sheet '$slug' konnte nicht gerendert werden:"
  printf '%s\n' "$render_out" | tail -3
fi

exit 0
