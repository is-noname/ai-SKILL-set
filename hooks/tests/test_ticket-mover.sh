#!/bin/bash
# Test fuer hooks/global/ticket-mover.sh — Schwerpunkt: der Bash-Zweig erkennt
# Python-/Heredoc-Schreibwege und relative Ticketpfade (IZG-T-158), ohne dass
# read-only-Befehle eine Verschiebung ausloesen.
# Baut ein Wegwerf-Projekt per init_tickets.sh in einem mktemp-Verzeichnis.
# Aufruf: bash hooks/tests/test_ticket-mover.sh (Exit 0 = alles gruen)
set -u
SCR="$(mktemp -d)"; trap 'rm -rf "$SCR"' EXIT

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO/hooks/global/ticket-mover.sh"
PROJ="$SCR/proj"

bash "$REPO/scripts/init_tickets.sh" "$PROJ" TST >/dev/null || { echo "FAIL init_tickets"; exit 1; }

mk() { # $1=nummer $2=status
  printf -- '---\nid: TST-T-%s\ntitle: t\nstatus: %s\ncreated: 2026-08-22\n---\n' "$1" "$2" \
    > "$PROJ/tickets/open/TST-T-$1_t.md"
}

call() { # $1=bash-command (aus $PROJ heraus ausgefuehrt)
  ( cd "$PROJ" && jq -n --arg c "$1" '{tool_name:"Bash", tool_input:{command:$c}}' | bash "$HOOK" )
}

check() { # $1=name $2=erwartet(moved|kept) $3=nummer
  local got=kept
  [ -f "$PROJ/tickets/done/2026/TST-T-$3_t.md" ] && got=moved
  if [ "$got" = "$2" ]; then echo "OK   $1 -> $got"; else echo "FAIL $1 -> $got (erwartet $2)"; FAILED=1; fi
}
FAILED=0

# AC: python-heredoc mit relativem Pfad — der bisher am Filter vorbeilaufende Fall
mk 001 done
call 'python3 - <<EOF
from pathlib import Path
p = Path("tickets/open/TST-T-001_t.md")
p.write_text(p.read_text())
EOF' >/dev/null 2>&1
check "1. python-heredoc write_text, relativer Pfad" moved 001

# AC: open(..., "w") als zweiter Python-Schreibweg
mk 002 done
call 'python3 -c "open(\"tickets/open/TST-T-002_t.md\", \"w\").write(x)"' >/dev/null 2>&1
check "2. open(...,w) auf Ticketdatei" moved 002

# Gegenprobe: read-only darf NICHT verschieben (sonst wuerde jedes cat auf ein
# fehlplatziertes Ticket eine stille Verschiebung ausloesen)
mk 003 done
call 'cat tickets/open/TST-T-003_t.md' >/dev/null 2>&1
check "3. cat (read-only) loest nicht aus" kept 003

# Regression: der bisher schon unterstuetzte sed -i-Weg bleibt erhalten
mk 004 done
call 'sed -i "s/x/y/" tickets/open/TST-T-004_t.md' >/dev/null 2>&1
check "4. sed -i (Bestandsweg)" moved 004

# Regression: absoluter Pfad wie ihn der Edit/Write-Zweig liefert
mk 005 done
( cd "$PROJ" && jq -n --arg f "$PROJ/tickets/open/TST-T-005_t.md" \
  '{tool_name:"Edit", tool_input:{file_path:$f}}' | bash "$HOOK" ) >/dev/null 2>&1
check "5. Edit-Zweig, absoluter Pfad" moved 005

# tickets.sh sync meldet einen unbrauchbaren Pfad, statt wortlos 0 zurueckzugeben
out="$(bash "$PROJ/scripts/tickets.sh" sync /etc/hostname 2>&1)"; rc=$?
if [ "$rc" -ne 0 ] && echo "$out" | grep -q "nicht in einem tickets/"; then
  echo "OK   6. sync meldet unbrauchbaren Pfad -> rc=$rc"
else
  echo "FAIL 6. sync bei unbrauchbarem Pfad -> rc=$rc, out='$out'"; FAILED=1
fi

# sync ohne Ziel verschiebt ALLE faelligen Tickets (frueher brach die Schleife
# nach der ersten Verschiebung ab, weil sync_one 1 zurueckgab und set -e griff)
mk 010 done; mk 011 done; mk 012 done
bash "$PROJ/scripts/tickets.sh" sync >/dev/null 2>&1
moved=0
for n in 010 011 012; do [ -f "$PROJ/tickets/done/2026/TST-T-${n}_t.md" ] && moved=$((moved+1)); done
if [ "$moved" -eq 3 ]; then
  echo "OK   7. sync ohne Ziel verschiebt alle 3"
else
  echo "FAIL 7. sync ohne Ziel verschob $moved von 3"; FAILED=1
fi

exit "$FAILED"
