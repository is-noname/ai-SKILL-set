#!/usr/bin/env bash
# Bootstraps tickets/ folder structure in the given directory (default: current dir)
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

Vollständige Konvention: `docs/tickets.md`

## Lookup-Reihenfolge
1. `in-progress/` — läuft noch was?
2. `open/` — nächste Arbeit
3. `blocked/` — nur wenn Blocker gezielt gelöst werden soll

## Dateiname
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Projekt-Kürzel aus `docs/doc-ids.md`.

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

# Deploy convention docs — repo version is authoritative.
# doc-ids.md is only copied if none exists yet (may contain project-specific prefixes).
REPO_ROOT="$(dirname "$0")/.."
mkdir -p "$TARGET/docs"

if [ ! -f "$TARGET/docs/doc-ids.md" ]; then
  cp "$REPO_ROOT/docs/doc-ids.md" "$TARGET/docs/doc-ids.md"
  echo "  doc-ids.md deployed to $TARGET/docs/"
else
  echo "  doc-ids.md already exists — skipped (repo version in $REPO_ROOT/docs/doc-ids.md)"
fi

cp "$REPO_ROOT/docs/tickets.md" "$TARGET/docs/tickets.md"
echo "  tickets.md deployed to $TARGET/docs/"

echo "tickets/ initialized in $TARGET (counter at 0, next_ticket_id.sh + docs deployed)"
