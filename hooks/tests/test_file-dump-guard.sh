#!/bin/bash
# Test fuer hooks/global/file-dump-guard.sh (IZG-T-126 Dateipfad, IZG-T-160 ls/find).
# Laeuft komplett in einem Wegwerf-Verzeichnis, fasst keine Projektdateien an.
# Aufruf: bash hooks/tests/test_file-dump-guard.sh   (Exit 0 = alles gruen)
# Anderen Hook pruefen: HOOK=/pfad/zu/file-dump-guard.sh bash ...
set -u

HOOK="${HOOK:-$(cd "$(dirname "$0")/../global" && pwd)/file-dump-guard.sh}"
[ -f "$HOOK" ] || { echo "Hook nicht gefunden: $HOOK"; exit 2; }

D="$(mktemp -d)"; trap 'rm -rf "$D"' EXIT
mkdir -p "$D/small" "$D/big" "$D/big/nested"
touch "$D/small/a" "$D/small/b" "$D/small/c"
for i in $(seq 1 60); do touch "$D/big/f$i"; done
seq 1 400 > "$D/big.txt"     # ueber MAX_LINES
seq 1 50  > "$D/small.txt"   # unter MAX_LINES

call() {
  python3 -c \
    "import json,sys; print(json.dumps({'tool_input':{'command':sys.argv[1]},'cwd':sys.argv[2]}))" \
    "$1" "$D" | bash "$HOOK"
}

FAILED=0
check() { # $1=erwartet(block|pass) $2=kommando
  local out got=pass
  out="$(call "$2")"
  echo "$out" | grep -q '"permissionDecision": *"deny"' && got=block
  if [ "$got" = "$1" ]; then
    echo "OK   $got  <- $2"
  else
    echo "FAIL $got (erwartet $1)  <- $2"; FAILED=1
  fi
}

echo "--- Dateipfad (cat/sed/head/tail, IZG-T-126) ---"
check block "cat $D/big.txt"
check pass  "cat $D/small.txt"
check block "sed -n '1,300p' $D/big.txt"
check block "sed -n 'p' $D/big.txt"
check pass  "sed -n '1,60p' $D/big.txt"
check pass  "sed -n '200,260p' $D/big.txt"
check block "head -200 $D/big.txt"
check pass  "head -40 $D/big.txt"
check pass  "cat $D/big.txt | grep 42"
check pass  "cat $D/big.txt | wc -l"
check block "cat $D/big.txt | grep -n ''"
check pass  "cat $D/big.txt > $D/kopie.txt"

echo "--- ls (IZG-T-160) ---"
check block "ls -la $D/big"
check block "ls -l $D/big"
check pass  "ls -la $D/small"
check pass  "ls $D/big"
check pass  "ls -la $D/big | head -20"
check pass  "ls -la $D/big | grep f1"
check pass  "ls -la $D/big | wc -l"
check block "ls -la $D/big | cat"
check block "ls -R $D"
check pass  "ls -la $D/nicht-vorhanden"
check pass  "ls -la $D/big/*.py"

echo "--- find (IZG-T-160) ---"
check block "find $D -type f"
check block "find $D"
check pass  "find $D -name '*.txt'"
check pass  "find $D -maxdepth 1"
check pass  "find $D -type f -exec grep -l 42 {} \\;"
check pass  "find $D -type f | head -20"
check pass  "find $D -type f | grep big"
check pass  "find $D -type f | wc -l"

echo "--- Schwellwerte ueberschreibbar ---"
if FILE_DUMP_GUARD_MAX_ENTRIES=200 bash -c \
   "python3 -c \"import json;print(json.dumps({'tool_input':{'command':'ls -la $D/big'},'cwd':'$D'}))\" | bash $HOOK" \
   | grep -q deny; then
  echo "FAIL MAX_ENTRIES=200 haette durchlassen muessen"; FAILED=1
else
  echo "OK   pass   <- ls -la big mit FILE_DUMP_GUARD_MAX_ENTRIES=200"
fi

echo
[ "$FAILED" = 0 ] && echo "alles gruen" || echo "Fehler siehe oben"
exit "$FAILED"
