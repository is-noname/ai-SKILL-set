#!/bin/bash
# Test fuer ~/.claude/hooks/tmux-context.sh (SessionStart meldet tmux-Kontext, IZG-T-168).
# Mockt das tmux-Binary, laeuft komplett auf Wegwerf-PATH.
# Aufruf: bash hooks/tests/test_tmux-context.sh (Exit 0 = alles gruen)
set -u
SCR="$(mktemp -d)"; trap 'rm -rf "$SCR"' EXIT

HOOK="$(dirname "$0")/../global/tmux-context.sh"
[ -f "$HOOK" ] || HOOK=/home/izg/.claude/hooks/tmux-context.sh

FAILED=0
check() { # $1=name $2=erwartete-teilstring $3=output
  if echo "$3" | grep -qF "$2"; then echo "OK   $1"; else echo "FAIL $1 -> $3 (erwartet: $2)"; FAILED=1; fi
}

# 1. Kein TMUX -> "tmux: nein"
out=$(echo '{}' | env -u TMUX bash "$HOOK")
check "1. ausserhalb tmux" '"tmux: nein"' "$out"

# 2. TMUX gesetzt, Mock mit 4 Panes, 3 davon frei
mkdir -p "$SCR/bin"
cat > "$SCR/bin/tmux" <<'EOF'
#!/bin/bash
case "$1" in
  display-message)
    echo "skillset:1.1 %0"
    ;;
  list-panes)
    printf '%%0 claude\n%%2 bash\n%%3 zsh\n%%6 fish\n'
    ;;
esac
EOF
chmod +x "$SCR/bin/tmux"
out=$(echo '{}' | PATH="$SCR/bin:$PATH" TMUX=dummy bash "$HOOK")
check "2. Session-Zeile" '"tmux: skillset:1.1 %0, 4 Panes (frei: %2 %3 %6)"' "$out"

# 3. TMUX gesetzt, keine freien Panes
cat > "$SCR/bin/tmux" <<'EOF'
#!/bin/bash
case "$1" in
  display-message) echo "skillset:1.1 %0" ;;
  list-panes) printf '%%0 claude\n%%1 vim\n' ;;
esac
EOF
out=$(echo '{}' | PATH="$SCR/bin:$PATH" TMUX=dummy bash "$HOOK")
check "3. keine freien Panes" '(frei: keine)' "$out"

# 4. TMUX gesetzt, aber tmux-Aufruf schlaegt fehl (z.B. Server weg) -> "tmux: nein"
cat > "$SCR/bin/tmux" <<'EOF'
#!/bin/bash
exit 1
EOF
out=$(echo '{}' | PATH="$SCR/bin:$PATH" TMUX=dummy bash "$HOOK")
check "4. tmux-Aufruf schlaegt fehl" '"tmux: nein"' "$out"

exit $FAILED
