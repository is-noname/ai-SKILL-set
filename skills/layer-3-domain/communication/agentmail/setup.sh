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
    # Platzhalterwerte leeren, sonst gilt die Pruefung als erfuellt, obwohl
    # noch "dein-agent@agentmail.to" drinsteht.
    sed -e 's|^AGENTMAIL_INBOX=.*|AGENTMAIL_INBOX=|' \
        -e 's|^AGENTMAIL_WEBHOOK_SECRET=.*|AGENTMAIL_WEBHOOK_SECRET=|' \
        env.example.txt > .env
    echo "  .env aus env.example.txt angelegt (Platzhalter geleert)"
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
missing=()
grep -q '^AGENTMAIL_API_KEY=.\+' .env || missing+=("AGENTMAIL_API_KEY (Key von agentmail.to)")
grep -q '^AGENTMAIL_INBOX=.\+' .env || missing+=("AGENTMAIL_INBOX (deine Inbox-Adresse)")

if [ ${#missing[@]} -gt 0 ]; then
    echo ""
    echo "Noch von Hand einzutragen in $SKILL_DIR/.env:"
    for entry in "${missing[@]}"; do
        echo "  - $entry"
    done
    exit 1
fi

echo "  Setup vollstaendig"
