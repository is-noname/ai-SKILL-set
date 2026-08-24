#!/bin/bash
# Test fuer ~/.claude/hooks/read-size-guard.sh (Token-Schaetzung, IZG-T-153).
# Laeuft komplett auf Wegwerf-Dateien in einem mktemp-Verzeichnis.
# Aufruf: bash hooks/tests/test_read-size-guard.sh (Exit 0 = alles gruen)
set -u
SCR="$(mktemp -d)"; trap 'rm -rf "$SCR"' EXIT

HOOK="$(dirname "$0")/../global/read-size-guard.sh"
[ -f "$HOOK" ] || HOOK=/home/izg/.claude/hooks/read-size-guard.sh

# Testdateien: Groesse in Bytes steuert die geschaetzten Tokens (4 Zeichen = 1 Token)
mk() { # $1=datei $2=zeilen $3=zeichen-pro-zeile
  local i line
  line=$(printf 'x%.0s' $(seq 1 "$3"))
  : > "$1"
  for ((i=0; i<$2; i++)); do echo "$line" >> "$1"; done
}
DENSE="$SCR/dense.py";  mk "$DENSE" 250 80    # 250 Zeilen, ~20 KB -> ~5.000 Tok
SPARSE="$SCR/sparse.md"; mk "$SPARSE" 400 5   # 400 Zeilen, ~2,4 KB -> ~600 Tok
MID="$SCR/mid.txt";     mk "$MID" 100 60      # ~6 KB -> ~1.500 Tok
LOG="$SCR/x.log";       mk "$LOG" 5 10
IMG="$SCR/x.png";       mk "$IMG" 500 80

call() { # $1=datei $2=offset|- $3=limit|-
  local extra=""
  [ "$2" != "-" ] && extra="$extra, \"offset\": $2"
  [ "$3" != "-" ] && extra="$extra, \"limit\": $3"
  printf '{"tool_name":"Read","tool_input":{"file_path":"%s"%s}}' "$1" "$extra" | bash "$HOOK"
}

check() { # $1=name $2=erwartet(pass|deny|hint) $3=output
  local got=pass
  echo "$3" | grep -q '"permissionDecision": *"deny"' && got=deny
  echo "$3" | grep -q 'additionalContext' && got=hint
  if [ "$got" = "$2" ]; then echo "OK   $1 -> $got"; else echo "FAIL $1 -> $got (erwartet $2)"; FAILED=1; fi
}
FAILED=0

# AC1: dichte Datei unter der alten 600-Zeilen-Schwelle wird jetzt geblockt
check "1. dichte Datei (250 Zeilen, ~5k Tok)" deny "$(call "$DENSE" - -)"
# AC2: viele kurze Zeilen, wenig Tokens -> durch, obwohl > 300 Zeilen
check "2. duenne Datei (400 Zeilen, ~600 Tok)" pass "$(call "$SPARSE" - -)"
check "3. mittlere Datei (~1,5k Tok)"          hint "$(call "$MID" - -)"

# AC3: Durchlaesse aus IZG-T-121
check "4. Teil-Read offset"        pass "$(call "$DENSE" 10 -)"
check "5. Teil-Read limit"         pass "$(call "$DENSE" - 50)"
check "6. Bild"                    pass "$(call "$IMG" - -)"
check "7. GUARD_OFF"               pass "$(READ_SIZE_GUARD_OFF=1 call "$DENSE" - -)"

# AC4: .log bleibt hart gesperrt, auch mit Ventil
check "8. .log"                    deny "$(call "$LOG" - -)"
check "9. .log trotz GUARD_OFF"    deny "$(READ_SIZE_GUARD_OFF=1 call "$LOG" - -)"

# AC5: alte Zeilenschwellen wirken weiter
check "10. alt MAX greift"         deny "$(READ_SIZE_GUARD_MAX=300 call "$SPARSE" - -)"
check "11. alt WARN greift"        hint "$(READ_SIZE_GUARD_WARN=300 call "$SPARSE" - -)"
check "12. alt MAX hoch -> Token"  pass "$(READ_SIZE_GUARD_MAX=9999 call "$SPARSE" - -)"

# Neue Schwellen konfigurierbar
check "13. MAX_TOKENS hoch"        hint "$(READ_SIZE_GUARD_MAX_TOKENS=99999 call "$DENSE" - -)"
check "14. WARN_TOKENS hoch"       pass "$(READ_SIZE_GUARD_WARN_TOKENS=99999 READ_SIZE_GUARD_MAX_TOKENS=99999 call "$DENSE" - -)"

# Nicht existierende Datei
check "15. fehlende Datei"         pass "$(call "$SCR/gibtsnicht.py" - -)"

exit $FAILED
