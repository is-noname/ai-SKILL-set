#!/usr/bin/env bash
# Bootstraps tickets/ folder structure in the given directory (default: current dir)
# For global agent setup (one-time, per machine) use: bash scripts/setup_global_tickets.sh
TARGET="${1:-.}"

if [ -d "$TARGET/tickets" ]; then
  echo "tickets/ already exists in $TARGET — nothing to do."
  exit 0
fi

mkdir -p "$TARGET/tickets/open" \
         "$TARGET/tickets/in-progress" \
         "$TARGET/tickets/blocked" \
         "$TARGET/tickets/done"

echo "0" > "$TARGET/tickets/.counter"

cat > "$TARGET/tickets/PROTOCOL.md" << 'EOF'
# Tickets

Vollständige Konvention: `tickets.md` im globalen Verzeichnis deines AI-Agenten.

## Lookup-Reihenfolge
1. `in-progress/` — läuft noch was?
2. `open/` — nächste Arbeit
3. `blocked/` — nur wenn Blocker gezielt gelöst werden soll

## Dateiname
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Projekt-Kürzel aus `doc-ids.md` im globalen Agent-Verzeichnis.

## Ticket-ID vergeben
```bash
bash scripts/next_ticket_id.sh {PRJ}
```

## Statuswechsel
`status:`-Feld im Frontmatter ändern — Hook verschiebt die Datei automatisch.
Verlaufseintrag pflegen: wann, warum, was erledigt/offen.
EOF

mkdir -p "$TARGET/scripts"

cat > "$TARGET/scripts/next_ticket_id.sh" << 'EOF'
#!/usr/bin/env bash
# Gibt die nächste Ticket-ID aus und inkrementiert den Zähler.
# Usage: bash scripts/next_ticket_id.sh IZG
PREFIX="${1:-PRJ}"
COUNTER_FILE="$(dirname "$0")/../tickets/.counter"

if [ ! -f "$COUNTER_FILE" ]; then
  echo "Fehler: tickets/.counter nicht gefunden. init_tickets.sh ausführen." >&2
  exit 1
fi

current=$(cat "$COUNTER_FILE")
next=$((current + 1))
echo "$next" > "$COUNTER_FILE"

printf "%s-T-%03d\n" "$PREFIX" "$next"
EOF

chmod +x "$TARGET/scripts/next_ticket_id.sh"

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
DEST="$(cd "$TARGET/scripts" && pwd)/init_tickets.sh"
if [ "$SELF" != "$DEST" ]; then
  cp "$0" "$TARGET/scripts/init_tickets.sh"
  chmod +x "$TARGET/scripts/init_tickets.sh"
fi

echo "tickets/ initialized in $TARGET (counter at 0, scripts deployed)"
