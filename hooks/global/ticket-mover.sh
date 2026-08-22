#!/bin/bash
# PostToolUse hook: duenner Adapter. Die Verschiebe-Logik lebt in tickets.sh sync
# (projekt-lokal, IZG-T-088) — dieser Hook extrahiert nur den betroffenen Dateipfad
# aus dem Claude-spezifischen PostToolUse-Payload und delegiert.

input=$(cat)

# Prefilter ohne Prozessstart: der weit ueberwiegende Teil aller Edit/Write/Bash-
# Aufrufe betrifft keine Ticketdatei. Ein Payload ohne "tickets/"-Substring kann in
# keinem der drei Zweige unten zu einem Treffer fuehren (Edit/Write pruefen den
# file_path direkt auf */tickets/*, der Bash-Zweig verlangt "tickets/" bereits im
# eigenen grep-Pattern) — also vor dem ersten jq-Fork abbrechen (IZG-T-104).
case "$input" in
  *tickets/*) ;;
  *) exit 0 ;;
esac

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
  # in-place sed/perl, Umlenkung nach tickets/, tee in tickets/ — und die
  # Python-Schreibwege (write_text/writelines/open(...,"w")), die typischerweise
  # per `python3 - <<EOF`-Heredoc kommen und bisher am Filter vorbeiliefen
  # (IZG-T-158). Bewusst NICHT dabei: mv/cp auf Ticketdateien — die sind laut
  # Konvention verboten, ein Treffer waere kein zu unterstuetzender Schreibweg.
  echo "$command" | grep -qE 'sed[[:space:]]+-i|perl[[:space:]]+-[A-Za-z]*i|>>?[[:space:]]*[^|&;]*tickets/|tee[[:space:]]+[^|&;]*tickets/|write_text\(|writelines\(|open\([^)]*['"'"'"][wa]' || exit 0
  # Ticket-Pfad aus dem Bash-Befehl extrahieren (erstes tickets/*.md ohne Quote/Space).
  # Das Segment vor "tickets/" ist optional: in Heredocs steht der Pfad oft relativ
  # (Path("tickets/open/X.md")), ein erzwungenes "/tickets/" fand den gar nicht.
  file_path=$(echo "$command" | grep -oE "[^ '\"]*tickets/[^ '\"]+\.md" | head -1)
  [[ -n "$file_path" && -f "$file_path" ]] || exit 0
  # Relativen Pfad absolut machen, sonst scheitert der */tickets/*-Test unten.
  file_path="$(readlink -f "$file_path" 2>/dev/null || echo "$file_path")"
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
