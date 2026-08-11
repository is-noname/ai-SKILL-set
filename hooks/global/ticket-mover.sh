#!/bin/bash
# PostToolUse hook: verschiebt Ticket-Dateien wenn status: im Frontmatter vom Ordner abweicht

input=$(cat)

tool_name=$(echo "$input" | jq -r '.tool_name // empty' 2>/dev/null)

if [[ "$tool_name" == "Edit" || "$tool_name" == "Write" ]]; then
  file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
  [[ -n "$file_path" && -f "$file_path" ]] || exit 0
elif [[ "$tool_name" == "Bash" ]]; then
  # Status wird manchmal per `sed -i` statt via Edit gesetzt — diesen Fall mitnehmen.
  command=$(echo "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
  # Nur bei TATSAECHLICH schreibenden Befehlen reagieren. Ein read-only Befehl
  # (cat/grep/less/head/git show) der eine Ticket-Datei nur liest, darf kein
  # Ticket verschieben — sonst wuerde z.B. `cat tickets/open/X.md` bei einem
  # fehlplatzierten Ticket eine stille Verschiebung ausloesen. Schreib-Indikatoren:
  # in-place sed/perl, Umlenkung nach tickets/, tee in tickets/.
  echo "$command" | grep -qE 'sed[[:space:]]+-i|perl[[:space:]]+-[A-Za-z]*i|>>?[[:space:]]*[^|&;]*tickets/|tee[[:space:]]+[^|&;]*tickets/' || exit 0
  # Ticket-Pfad aus dem Bash-Befehl extrahieren (erstes tickets/*.md ohne Quote/Space)
  file_path=$(echo "$command" | grep -oE "[^ '\"]+/tickets/[^ '\"]+\.md" | head -1)
  [[ -n "$file_path" && -f "$file_path" ]] || exit 0
else
  exit 0
fi

# Nur Dateien innerhalb eines tickets/-Verzeichnisses
[[ "$file_path" == */tickets/* ]] || exit 0

# Muss gültiges Ticket-Frontmatter haben (id: PRJ-T-NNN)
grep -qE "^id: [A-Z]+-T-[0-9]+" "$file_path" || exit 0

# status:-Feld auslesen
status=$(grep -m1 "^status: " "$file_path" | sed 's/^status: //' | tr -d '[:space:]"'"'")
[[ -n "$status" ]] || exit 0

# Nur bekannte Status-Werte
case "$status" in
  open|in-progress|blocked|done) ;;
  *) exit 0 ;;
esac

current_dir=$(dirname "$file_path")
current_folder=$(basename "$current_dir")
filename=$(basename "$file_path")

if [[ "$status" == "done" ]]; then
  # done/ ist Archiv, nach Jahr unterteilt (IZG-T-084): Jahr kommt aus dem
  # created:-Feld des Tickets, Fallback aktuelles Jahr falls das Feld fehlt.
  year=$(grep -m1 "^created: " "$file_path" | sed 's/^created: //' | grep -oE "^[0-9]{4}" || true)
  [[ -n "$year" ]] || year=$(date +%Y)

  # tickets_root ermitteln: liegt die Datei schon in done/<jahr>/, ist current_dir
  # bereits tickets_root/done/<jahr> (zwei Ebenen ueber tickets_root).
  if [[ "$current_folder" =~ ^[0-9]{4}$ ]] && [[ "$(basename "$(dirname "$current_dir")")" == "done" ]]; then
    tickets_root=$(dirname "$(dirname "$current_dir")")
  else
    tickets_root=$(dirname "$current_dir")
  fi
  target_dir="$tickets_root/done/$year"

  # Nichts zu tun wenn Ordner schon stimmt
  [[ "$current_dir" == "$target_dir" ]] && exit 0
else
  # Nichts zu tun wenn Ordner schon stimmt
  [[ "$current_folder" == "$status" ]] && exit 0

  tickets_root=$(dirname "$current_dir")
  target_dir="$tickets_root/$status"
fi

mkdir -p "$target_dir"

# Kollisionsschutz: nie ein vorhandenes Ziel überschreiben (z.B. gleiche ID in
# zwei Ordnern durch manuelles Verschieben).
if [[ -e "$target_dir/$filename" ]]; then
  # Inhalt vergleichen: Ist die Quelle eine exakte Dublette des Ziels, war die
  # status:-Änderung nur redundant — dann die Quelle löschen. Sonst bliebe der
  # status:/Ordner-Widerspruch bestehen und JEDER Folge-Edit würde denselben
  # Kollisions-Warnhinweis re-triggern (IZG-T-050). Unterscheiden sich die
  # Inhalte, liegt ein echter ID-Konflikt (zwei verschiedene Tickets, gleiche ID)
  # vor — den lassen wir stehen und warnen weiterhin, da manuelle Prüfung nötig.
  if cmp -s "$file_path" "$target_dir/$filename"; then
    rm -f "$file_path"
    msg="[ticket-mover] $filename: identische Dublette in $status/ gefunden — Quelle in $current_folder/ entfernt. Datei liegt jetzt unter $target_dir/."
    echo "$msg" >&2
    jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
    exit 0
  fi
  msg="[ticket-mover] $filename: Ziel $status/ existiert bereits mit ABWEICHENDEM Inhalt — nicht verschoben (echter ID-Konflikt). Bitte manuell zusammenführen: die ID $filename existiert doppelt mit unterschiedlichem Inhalt."
  echo "$msg" >&2
  jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
  exit 0
fi

mv -n "$file_path" "$target_dir/$filename"

# Stdout-Feedback an den Agent: ohne dies sieht er nur stderr nicht und versucht
# einen manuellen mv auf die bereits verschobene Datei (siehe IZG-T-039).
msg="[ticket-mover] $filename automatisch von $current_folder/ nach $status/ verschoben. Datei liegt jetzt unter $target_dir/ — kein manueller mv nötig."
echo "$msg" >&2
jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
