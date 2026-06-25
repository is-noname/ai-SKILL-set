#!/usr/bin/env bash
# Bootstraps tickets/ folder structure in the given directory (default: current dir)
TARGET="${1:-.}"
REPO_ROOT="$(dirname "$0")/.."
RAW_BASE="https://raw.githubusercontent.com/is-noname/ai-SKILL-set/main"

# --- Global infrastructure ---
# Each AI agent has its own global config dir and a different entrypoint file.
# tickets.md + doc-ids.md are deployed to every agent dir that exists.
# Claude supports @file includes; others get an inline Ticketsystem block.

declare -A AGENT_CONFIGS=(
  ["$HOME/.claude"]="CLAUDE.md"
  ["$HOME/.codex"]="instructions.md"
  ["$HOME/.gemini"]="GEMINI.md"
  ["$HOME/.vibe"]="AGENTS.md"
)

_fetch_doc() {
  local name="$1" dest="$2"
  if [ -f "$REPO_ROOT/docs/$name" ]; then
    cp "$REPO_ROOT/docs/$name" "$dest"
  else
    curl -fsSL "$RAW_BASE/docs/$name" -o "$dest"
  fi
}

_patch_claude() {
  local cfg="$1"
  if ! grep -q "^@tickets.md" "$cfg"; then
    printf '\n## Ticketsystem\n\nBei Projektarbeit zuerst `tickets/in-progress/` prüfen — läuft noch etwas?\n\n@tickets.md\n' >> "$cfg"
    echo "  patched: $cfg (@tickets.md include)"
  fi
}

_patch_generic() {
  local cfg="$1" dir="$2"
  if ! grep -q "tickets/in-progress" "$cfg"; then
    cat >> "$cfg" << BLOCK

## Ticketsystem

Bei Projektarbeit zuerst \`tickets/in-progress/\` prüfen — läuft noch etwas?
Vollständige Konvention: \`$dir/tickets.md\`

Lookup-Reihenfolge:
1. \`tickets/in-progress/\` — läuft noch was?
2. \`tickets/open/\` — nächste Arbeit
3. \`tickets/blocked/\` — nur wenn Blocker gezielt gelöst werden soll

Ticket-ID via \`bash scripts/next_ticket_id.sh {PRJ}\`.
Status-Feld im Frontmatter ändern — Hook verschiebt die Datei automatisch.
BLOCK
    echo "  patched: $cfg (inline Ticketsystem block)"
  fi
}

for dir in "${!AGENT_CONFIGS[@]}"; do
  cfg_file="${AGENT_CONFIGS[$dir]}"
  cfg="$dir/$cfg_file"
  [ -d "$dir" ] || continue

  # Deploy docs
  for doc in tickets.md doc-ids.md; do
    dest="$dir/$doc"
    if [ -f "$dest" ]; then
      echo "  $dest already exists — skipped"
    else
      _fetch_doc "$doc" "$dest"
      echo "  deployed: $dest"
    fi
  done

  # Patch config if it exists
  if [ -f "$cfg" ]; then
    if [[ "$cfg_file" == "CLAUDE.md" ]]; then
      _patch_claude "$cfg"
    else
      _patch_generic "$cfg" "$dir"
    fi
  else
    echo "  $cfg not found — skipping patch"
  fi
done

# --- Project-local structure ---
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
