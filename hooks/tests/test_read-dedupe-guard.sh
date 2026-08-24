#!/bin/bash
# Test fuer ~/.claude/hooks/read-dedupe-guard.sh. Laeuft in einer Wegwerf-HOME-Umgebung,
# fasst weder den echten State unter ~/.claude/state/read-dedupe/ noch Projektdateien an.
# Aufruf: bash ~/.claude/hooks/tests/test_read-dedupe-guard.sh (Exit 0 = alles gruen)
# Testet read-dedupe-guard.sh gegen eine isolierte HOME-Umgebung.
set -u
SCR="$(mktemp -d)"; trap 'rm -rf "$SCR"' EXIT
export HOME="$SCR/testhome"
rm -rf "$HOME"; mkdir -p "$HOME/.claude/state"

HOOK=/home/izg/.claude/hooks/read-dedupe-guard.sh
TARGET="$SCR/target.txt"; printf 'zeile\n%.0s' $(seq 1 50) > "$TARGET"
TRANS="$SCR/transcript.jsonl"; : > "$TRANS"
SID=testsession

lines() { printf '{"x":1}\n%.0s' $(seq 1 "$1") >> "$TRANS"; }
call() { # $1=offset|-  $2=limit|-
  local o="$1" l="$2" extra=""
  [ "$o" != "-" ] && extra="$extra, \"offset\": $o"
  [ "$l" != "-" ] && extra="$extra, \"limit\": $l"
  printf '{"session_id":"%s","transcript_path":"%s","tool_name":"Read","tool_input":{"file_path":"%s"%s}}' \
    "$SID" "$TRANS" "$TARGET" "$extra" | bash "$HOOK"
}
check() { # $1=name $2=erwartet(pass|deny|hint) $3=output
  local got=pass
  echo "$3" | grep -q '"permissionDecision": *"deny"' && got=deny
  echo "$3" | grep -q 'additionalContext' && got=hint
  if [ "$got" = "$2" ]; then echo "OK   $1 -> $got"; else echo "FAIL $1 -> $got (erwartet $2)"; FAILED=1; fi
}
FAILED=0

lines 10
check "1. Voll-Read"                pass "$(call - -)"
lines 5
check "2. Voll-Read im Fenster"     deny "$(call - -)"
check "3. Teil-Read im Fenster"     deny "$(call 10 5)"
lines 400
check "4. Voll-Read ausser Fenster" hint "$(call - -)"
check "5. gleich danach wieder frisch" deny "$(call - -)"

# Datei geaendert -> durchlassen
rm -rf "$HOME/.claude/state"; : > "$TRANS"; lines 10
check "6. Erstread"                 pass "$(call - -)"
sleep 1; echo neu >> "$TARGET"; lines 5
check "7. nach Aenderung"           pass "$(call - -)"
check "8. direkt danach erneut"     deny "$(call - -)"

# Teil-Read ohne vorherigen Voll-Read wird nicht gemerkt
rm -rf "$HOME/.claude/state"; : > "$TRANS"; lines 10
check "9. Teil-Read erst"           pass "$(call 1 20)"
lines 3
check "10. Teil-Read weiter"        pass "$(call 20 20)"
check "11. Voll-Read danach"        pass "$(call - -)"

# Ventile
rm -rf "$HOME/.claude/state"; : > "$TRANS"; lines 10
call - - >/dev/null; lines 2
check "12. WINDOW=0 -> Hinweis"     hint "$(READ_DEDUPE_GUARD_WINDOW=0 call - -)"
rm -rf "$HOME/.claude/state"; call - - >/dev/null
check "13. GUARD_OFF"               pass "$(READ_DEDUPE_GUARD_OFF=1 call - -)"

# ohne transcript_path kein Block
rm -rf "$HOME/.claude/state"
printf '{"session_id":"%s","tool_name":"Read","tool_input":{"file_path":"%s"}}' "$SID" "$TARGET" | bash "$HOOK" >/dev/null
out=$(printf '{"session_id":"%s","tool_name":"Read","tool_input":{"file_path":"%s"}}' "$SID" "$TARGET" | bash "$HOOK")
check "14. ohne transcript_path"    hint "$out"

exit $FAILED
