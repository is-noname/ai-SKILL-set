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

# RAW_BASE-Reihenfolge:
#   1. Env AISKILLSET_RAW_BASE (explizit überschreibbar)
#   2. aus dem git-Remote von REPO_ROOT abgeleitet (GitHub https/ssh)
#   3. hartkodierter Default als letzter Ausweg
# Greift nur, wenn der lokale docs/-Pfad fehlt (siehe _fetch_doc).
default_raw_base="https://raw.githubusercontent.com/is-noname/ai-SKILL-set/main"
RAW_BASE="${AISKILLSET_RAW_BASE:-}"
if [ -z "$RAW_BASE" ]; then
  remote_url="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)"
  if [ -n "$remote_url" ]; then
    branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
    [ "$branch" = "HEAD" ] && branch=main
    # owner/repo aus https- oder ssh-Form extrahieren, .git entfernen
    slug="$(printf '%s' "$remote_url" \
      | sed -E -e 's#^git@[^:]+:##' -e 's#^https?://[^/]+/##' -e 's#\.git$##')"
    [ -n "$slug" ] && RAW_BASE="https://raw.githubusercontent.com/$slug/$branch"
  fi
  RAW_BASE="${RAW_BASE:-$default_raw_base}"
fi

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
    return 0
  fi
  if command -v curl >/dev/null 2>&1 && curl -fsSL "$RAW_BASE/docs/$name" -o "$dest"; then
    return 0
  fi
  rm -f "$dest"  # curl -o legt bei Fehler ggf. eine leere Datei an
  echo "Error: '$name' konnte weder lokal ($REPO_ROOT/docs/$name) noch via Remote" >&2
  echo "       ($RAW_BASE/docs/$name) bezogen werden." >&2
  echo "       Repo lokal auschecken oder AISKILLSET_RAW_BASE auf eine erreichbare Quelle setzen." >&2
  return 1
}

for doc in tickets.md doc-ids.md; do
  dest="$AGENT_DIR/$doc"
  if [ -f "$dest" ]; then
    echo "  $dest already exists — skipped"
  elif _fetch_doc "$doc" "$dest"; then
    echo "  deployed: $dest"
  else
    exit 1
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
