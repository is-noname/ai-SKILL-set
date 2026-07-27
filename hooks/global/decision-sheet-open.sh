#!/bin/bash
# Stop hook: oeffnet ein neu geschriebenes Decision Sheet, sobald der Agent fertig ist.
#
# Bewusst als Stop-Hook und nicht als PostToolUse: so ist es egal, WIE das Sheet
# entstanden ist (Write, Edit, Bash-Heredoc, Script) - der Hook schaut nur, ob in
# <projekt>/.decisions/ ein Sheet liegt, das noch nicht beantwortet und noch nicht
# geoeffnet wurde. Und er feuert erst, wenn der Agent zu Ende geredet hat, statt
# mitten im Turn ein Fenster aufzureissen.
#
# Gegenstueck: decision-answers.sh holt die Antworten zurueck (#answers).
# Gehoert zum Skill skills/layer-1-base/decision-sheet.

input=$(cat)

project=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
[[ -n "$CLAUDE_PROJECT_DIR" ]] && project="$CLAUDE_PROJECT_DIR"
[[ -n "$project" && -d "$project" ]] || project="$PWD"

dir="$project/.decisions"
[[ -d "$dir" ]] || exit 0

renderer="$HOME/ai-shared/decision-sheet/render_sheet.py"
[[ -f "$renderer" ]] || exit 0

stamp="$dir/.opened"
touch "$stamp" 2>/dev/null || exit 0

# Neuestes Sheet zuerst - pro Turn wird maximal ein Fenster geoeffnet.
while read -r sheet; do
  [[ -n "$sheet" ]] || continue
  slug=$(basename "$sheet" .jsonl)
  answers="$dir/$slug.answers.json"

  # Schon beantwortet (Antworten neuer als das Sheet)? Dann ist es durch.
  [[ -f "$answers" && "$answers" -nt "$sheet" ]] && continue

  # Schon geoeffnet? Der Stempel haelt Pfad + mtime fest, damit ein GEAENDERTES
  # Sheet wieder aufgeht, ein unveraendertes aber nicht bei jedem Turn erneut.
  # Nanosekunden-Auflaesung (%.9Y), nicht %Y: eine Korrektur direkt nach dem
  # Stempeln faellt sonst in dieselbe Sekunde und das Sheet gilt als unveraendert.
  mtime=$(stat -c %.9Y "$sheet" 2>/dev/null || stat -c %Y "$sheet" 2>/dev/null)
  grep -qxF "$sheet $mtime" "$stamp" 2>/dev/null && continue

  render_out=$(python3 "$renderer" "$sheet" 2>&1)
  render_rc=$?

  # Stempeln passiert in BEIDEN Faellen: sonst wiederholt ein defektes Sheet seine
  # Fehlermeldung in jedem Turn. Wird es korrigiert, aendert sich die mtime und der
  # Hook nimmt es erneut dran. Alten Eintrag ersetzen, damit der Stempel nicht waechst.
  grep -vF "$sheet " "$stamp" > "$stamp.tmp" 2>/dev/null
  mv -f "$stamp.tmp" "$stamp" 2>/dev/null
  printf '%s %s\n' "$sheet" "$mtime" >> "$stamp"

  if [[ $render_rc -eq 0 ]]; then
    echo "Decision Sheet geoeffnet: $slug ($(grep -c . "$sheet") Zeilen)"
  else
    # Sheet ist defekt - Validator-Meldung durchreichen, damit sie im Transkript steht.
    echo "Decision Sheet '$slug' konnte nicht gerendert werden:"
    printf '%s\n' "$render_out" | tail -3
  fi
  break
done < <(find "$dir" -maxdepth 1 -name '*.jsonl' -type f -printf '%T@ %p\n' 2>/dev/null \
           | sort -rn | cut -d' ' -f2-)

exit 0
