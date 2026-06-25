#!/usr/bin/env bash
# One-time global setup: deploys tickets.md + doc-ids.md to all AI agent dirs
# and patches their global config files.
# Run once per machine, not per project.
REPO_ROOT="$(dirname "$0")/.."
RAW_BASE="https://raw.githubusercontent.com/is-noname/ai-SKILL-set/main"

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

Vollständige Konvention: \`$dir/tickets.md\`

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
  fi
}

for dir in "${!AGENT_CONFIGS[@]}"; do
  cfg_file="${AGENT_CONFIGS[$dir]}"
  cfg="$dir/$cfg_file"
  [ -d "$dir" ] || continue

  for doc in tickets.md doc-ids.md; do
    dest="$dir/$doc"
    if [ -f "$dest" ]; then
      echo "  $dest already exists — skipped"
    else
      _fetch_doc "$doc" "$dest"
      echo "  deployed: $dest"
    fi
  done

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

echo "Global ticket infrastructure ready."
