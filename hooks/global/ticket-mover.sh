#!/bin/bash
# PostToolUse hook: duenner Adapter. Die Verschiebe-Logik lebt in tickets.sh sync
# (projekt-lokal, IZG-T-088) — dieser Hook extrahiert nur den betroffenen Dateipfad
# aus dem Claude-spezifischen PostToolUse-Payload und delegiert.

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

# Projekt-lokales tickets.sh finden: <projekt-root>/scripts/tickets.sh, wobei
# <projekt-root> alles vor dem "/tickets/"-Segment im Dateipfad ist.
tickets_root="${file_path%%/tickets/*}"
tickets_sh="$tickets_root/scripts/tickets.sh"
[[ -x "$tickets_sh" ]] || exit 0

msg="$("$tickets_sh" sync "$file_path" 2>&1)"
[[ -n "$msg" ]] || exit 0

# Stdout-Feedback an den Agent: ohne dies sieht er nur stderr nicht und versucht
# einen manuellen mv auf die bereits verschobene Datei (siehe IZG-T-039).
echo "[ticket-mover] $msg" >&2
jq -n --arg m "[ticket-mover] $msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
