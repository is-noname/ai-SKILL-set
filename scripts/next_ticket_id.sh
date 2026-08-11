#!/usr/bin/env bash
# Dünner Wrapper: die Logik lebt in tickets.sh next (IZG-T-083). Bleibt als eigene
# Datei bestehen, weil die Konvention (docs/tickets.md, PROTOCOL.md) sie
# projektweit als ID-Vergabe-Kommando referenziert.
# Usage: bash scripts/next_ticket_id.sh IZG
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/tickets.sh" next "$@"
