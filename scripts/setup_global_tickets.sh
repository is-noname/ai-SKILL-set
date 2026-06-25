#!/usr/bin/env bash
# One-time global setup for a single AI agent dir.
# Each agent runs this for itself only.
# Usage: bash setup_global_tickets.sh ~/.vibe
#
# Agent dir → config file mapping:
#   ~/.claude  → CLAUDE.md
#   ~/.codex   → instructions.md
#   ~/.gemini  → GEMINI.md
#   ~/.vibe    → AGENTS.md

AGENT_DIR="${1}"
REPO_ROOT="$(dirname "$0")/.."
RAW_BASE="https://raw.githubusercontent.com/is-noname/ai-SKILL-set/main"

if [ -z "$AGENT_DIR" ]; then
  echo "Usage: bash setup_global_tickets.sh <agent-dir>" >&2
  echo "  e.g. bash setup_global_tickets.sh ~/.vibe" >&2
  exit 1
fi

AGENT_DIR="$(eval echo "$AGENT_DIR")"  # expand ~ if passed as literal

if [ ! -d "$AGENT_DIR" ]; then
  echo "Error: $AGENT_DIR does not exist." >&2
  exit 1
fi

declare -A CFG_MAP=(
  [".claude"]="CLAUDE.md"
  [".codex"]="instructions.md"
  [".gemini"]="GEMINI.md"
  [".vibe"]="AGENTS.md"
)

agent_name="$(basename "$AGENT_DIR")"
cfg_file="${CFG_MAP[$agent_name]}"

if [ -z "$cfg_file" ]; then
  echo "Unknown agent dir '$agent_name'. Supported: .claude .codex .gemini .vibe" >&2
  exit 1
fi

_fetch_doc() {
  local name="$1" dest="$2"
  if [ -f "$REPO_ROOT/docs/$name" ]; then
    cp "$REPO_ROOT/docs/$name" "$dest"
  else
    curl -fsSL "$RAW_BASE/docs/$name" -o "$dest"
  fi
}

for doc in tickets.md doc-ids.md; do
  dest="$AGENT_DIR/$doc"
  if [ -f "$dest" ]; then
    echo "  $dest already exists — skipped"
  else
    _fetch_doc "$doc" "$dest"
    echo "  deployed: $dest"
  fi
done

cfg="$AGENT_DIR/$cfg_file"
if [ ! -f "$cfg" ]; then
  echo "  $cfg not found — skipping patch"
  exit 0
fi

if [ "$cfg_file" = "CLAUDE.md" ]; then
  if ! grep -q "^@tickets.md" "$cfg"; then
    printf '\n## Ticketsystem\n\nBei Projektarbeit zuerst `tickets/in-progress/` prüfen — läuft noch etwas?\n\n@tickets.md\n' >> "$cfg"
    echo "  patched: $cfg (@tickets.md include)"
  else
    echo "  $cfg already patched — skipped"
  fi
else
  if ! grep -q "tickets/in-progress" "$cfg"; then
    cat >> "$cfg" << BLOCK

## Ticketsystem

Vollständige Konvention: \`$AGENT_DIR/tickets.md\`

Lookup-Reihenfolge:
1. \`tickets/in-progress/\` — läuft noch was?
2. \`tickets/open/\` — nächste Arbeit
3. \`tickets/blocked/\` — nur wenn Blocker gezielt gelöst werden soll

Ticket-ID via \`bash scripts/next_ticket_id.sh {PRJ}\`.
Status-Feld im Frontmatter ändern — Hook verschiebt die Datei automatisch.

Neues Projekt bootstrappen:
\`\`\`bash
bash ~/.claude/scripts/init_tickets.sh /pfad/zum/projekt
\`\`\`
BLOCK
    echo "  patched: $cfg (inline Ticketsystem block)"
  else
    echo "  $cfg already patched — skipped"
  fi
fi

echo "Done: $AGENT_DIR"
