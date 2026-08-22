#!/usr/bin/env bash
# Richtet die externen Voraussetzungen aus requires.json ein, soweit automatisierbar.
# Wird von pull_skill.py bei --setup aufgerufen (cwd = Skill-Verzeichnis).
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SKILL_DIR"

echo "agentmail-Setup in $SKILL_DIR"

# --- .env aus der Vorlage anlegen (nie ueberschreiben) ---
if [ -f .env ]; then
    echo "  .env existiert bereits — unveraendert gelassen"
else
    # Platzhalter bleiben stehen: pull_skill.py erkennt unveraenderte Werte aus
    # env.example.txt als "nicht gesetzt" (IZG-T-157). Sie zeigen dem Nutzer,
    # welche Form der Wert haben soll.
    cp env.example.txt .env
    echo "  .env aus env.example.txt angelegt"
fi

# --- requests ---
if python3 -c "import requests" >/dev/null 2>&1; then
    echo "  Python-Paket 'requests' vorhanden"
else
    echo "  installiere 'requests'..."
    if ! python3 -m pip install --user requests; then
        echo "  ! pip-Installation fehlgeschlagen." >&2
        echo "    Manuell nachholen, z.B. im venv des Projekts: pip install requests" >&2
    fi
fi

# --- Was der Mensch noch selbst tun muss ---
# Leer ODER unveraendert aus der Vorlage zaehlt beides als "fehlt" — gleiche
# Semantik wie die env-Pruefung in pull_skill.py.
ist_gesetzt() {
    local var="$1" wert vorlage
    wert="$(sed -n "s|^${var}=||p" .env | head -1)"
    vorlage="$(sed -n "s|^${var}=||p" env.example.txt | head -1)"
    [ -n "$wert" ] && [ "$wert" != "$vorlage" ]
}

missing=()
ist_gesetzt AGENTMAIL_API_KEY || missing+=("AGENTMAIL_API_KEY (Key von agentmail.to)")
ist_gesetzt AGENTMAIL_INBOX || missing+=("AGENTMAIL_INBOX (deine Inbox-Adresse)")

if [ ${#missing[@]} -gt 0 ]; then
    echo ""
    echo "Noch von Hand einzutragen in $SKILL_DIR/.env:"
    for entry in "${missing[@]}"; do
        echo "  - $entry"
    done
    exit 1
fi

echo "  Setup vollstaendig"
