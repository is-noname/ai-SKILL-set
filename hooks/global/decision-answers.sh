#!/bin/bash
# UserPromptSubmit hook: holt exportierte Decision-Sheet-Antworten ab.
#
# Trigger: der Marker "#answers" irgendwo im Prompt (optional mit Slug:
# "#answers ticketsystem-v2"). Ohne Marker macht der Hook nichts.
#
# Ablauf: neueste *.answers.json aus ~/Downloads (bzw. ~/Downloads-Varianten)
# suchen, nach <projekt>/.decisions/ verschieben und den Inhalt auf stdout
# ausgeben - stdout eines UserPromptSubmit-Hooks landet im Kontext des Agenten.
#
# Gehoert zum Skill skills/layer-1-base/decision-sheet (siehe dessen SKILL.md).

input=$(cat)

prompt=$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)
[[ "$prompt" == *"#answers"* ]] || exit 0

project=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
[[ -n "$CLAUDE_PROJECT_DIR" ]] && project="$CLAUDE_PROJECT_DIR"
[[ -n "$project" && -d "$project" ]] || project="$PWD"

# Optionaler Slug direkt hinter dem Marker: "#answers mein-sheet"
slug=$(printf '%s' "$prompt" | sed -n 's/.*#answers[[:space:]]\{1,\}\([A-Za-z0-9._-]\{1,\}\).*/\1/p' | head -1)
pattern="${slug:-*}"
pattern="${pattern%.answers.json}"

# Download-Verzeichnisse: XDG plus deutsche und englische Variante. Dedupliziert,
# weil xdg-user-dir meist dasselbe Verzeichnis wie ~/Downloads liefert und find
# sonst jeden Treffer doppelt meldet.
dl_dirs=()
_add_dl() {
  [[ -n "$1" && -d "$1" ]] || return 0
  local existing
  for existing in "${dl_dirs[@]}"; do
    [[ "$existing" -ef "$1" ]] && return 0
  done
  dl_dirs+=("$1")
}
_add_dl "$(xdg-user-dir DOWNLOAD 2>/dev/null)"
_add_dl "$HOME/Downloads"
_add_dl "$HOME/Download"

target_dir="$project/.decisions"
found=""
if [[ ${#dl_dirs[@]} -gt 0 ]]; then
  # Neueste passende Datei ueber alle Kandidaten-Verzeichnisse hinweg.
  found=$(find "${dl_dirs[@]}" -maxdepth 1 -name "${pattern}.answers.json" -type f \
            -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
fi

if [[ -n "$found" ]]; then
  mkdir -p "$target_dir"
  base=$(basename "$found")
  # Chrome haengt bei Namenskollision " (1)" an - auf den Basisnamen zurueckfuehren.
  clean=$(printf '%s' "$base" | sed -E 's/ \([0-9]+\)\.answers\.json$/.answers.json/')
  dest="$target_dir/$clean"
  if mv -f "$found" "$dest" 2>/dev/null; then
    answers="$dest"
  else
    answers="$found"
    echo "Hinweis: Verschieben nach $dest fehlgeschlagen, Datei liegt noch unter $found."
  fi
else
  # Nichts Neues im Download-Ordner - vielleicht wurde schon manuell abgelegt.
  answers=$(find "$target_dir" -maxdepth 1 -name "${pattern}.answers.json" -type f \
              -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
fi

if [[ -z "$answers" || ! -f "$answers" ]]; then
  echo "Keine Antwort-Datei gefunden (gesucht: ${pattern}.answers.json in ${dl_dirs[*]:-<kein Download-Ordner>} und $target_dir)."
  echo "Im Renderer auf 'Export' -> 'Datei speichern' klicken, dann erneut #answers."
  exit 0
fi

sheet="${answers%.answers.json}.jsonl"
echo "Decision-Sheet-Antworten aus: $answers"
[[ -f "$sheet" ]] && echo "Zugehoeriges Sheet: $sheet"
echo "Leere Map in \"a\" = alle Empfehlungen uebernommen. [wert, notiz] = Auswahl plus Ergaenzung."
cat "$answers"
echo
exit 0
