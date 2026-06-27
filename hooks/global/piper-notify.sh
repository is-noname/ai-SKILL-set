#!/bin/bash
# TTS-Benachrichtigung via Piper wenn Claude auf Input wartet
source ~/.config/piper/defaults

INPUT=$(cat)
NOTIFICATION_TYPE=$(python3 -c "
import sys, json
try:
    d = json.loads('''$INPUT'''.replace(\"'\", '\"'))
    print(d.get('notification_type', 'unknown'))
except:
    # Fallback: direkt von stdin lesen geht nicht mehr, aber Input war leer
    print('unknown')
" 2>/dev/null)

# Robuster: JSON via Tempfile parsen
TMPFILE=$(mktemp)
echo "$INPUT" > "$TMPFILE"
NOTIFICATION_TYPE=$(python3 -c "
import sys, json
try:
    with open('$TMPFILE') as f:
        d = json.load(f)
    print(d.get('notification_type', ''))
except:
    print('')
" 2>/dev/null)
rm -f "$TMPFILE"

# Nur bei permission_prompt sprechen (Agent braucht Aufmerksamkeit)
# idle_prompt und auth_success ueberspringen
if [[ "$NOTIFICATION_TYPE" == "permission_prompt" ]]; then
    SAMPLE_RATE=$(python3 -c "import json; print(json.load(open('${PIPER_MODEL_DE}.json'))['audio']['sample_rate'])" 2>/dev/null || echo 22050)
    echo "Agent wartet auf Eingabe" | piper \
        --model "$PIPER_MODEL_DE" \
        --noise-scale "$PIPER_NOISE_SCALE" \
        --noise-w "$PIPER_NOISE_W" \
        --length-scale "${PIPER_LENGTH_SCALE:-1.0}" \
        --sentence-silence "$PIPER_SENTENCE_SILENCE" \
        --output_raw 2>/dev/null | aplay -r "$SAMPLE_RATE" -f S16_LE -t raw - 2>/dev/null &
fi

exit 0
