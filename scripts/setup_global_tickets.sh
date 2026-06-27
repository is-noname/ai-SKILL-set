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

# Holt eine Datei aus dem Repo: erst lokal aus REPO_ROOT/<relpath>, sonst via curl
# aus RAW_BASE/<relpath>. relpath ist repo-relativ (z.B. "docs/tickets.md").
_fetch() {
  local relpath="$1" dest="$2"
  if [ -f "$REPO_ROOT/$relpath" ]; then
    cp "$REPO_ROOT/$relpath" "$dest"
    return 0
  fi
  if command -v curl >/dev/null 2>&1 && curl -fsSL "$RAW_BASE/$relpath" -o "$dest"; then
    return 0
  fi
  rm -f "$dest"  # curl -o legt bei Fehler ggf. eine leere Datei an
  echo "Error: '$relpath' konnte weder lokal ($REPO_ROOT/$relpath) noch via Remote" >&2
  echo "       ($RAW_BASE/$relpath) bezogen werden." >&2
  echo "       Repo lokal auschecken oder AISKILLSET_RAW_BASE auf eine erreichbare Quelle setzen." >&2
  return 1
}

# tickets.md ist reine Konvention ohne user-spezifischen State → immer (neu)
# schreiben, damit Bestands-Agents die aktuelle Version bekommen (idempotent).
dest="$AGENT_DIR/tickets.md"
if _fetch "docs/tickets.md" "$dest"; then
  echo "  deployed: $dest"
else
  exit 1
fi

# Einmalige Migration: Älteres doc-ids.md trug die Kürzel-Registry inline. Bevor
# wir doc-ids.md (jetzt reine Konvention) überschreiben, die Kürzel verlustfrei nach
# project-identifier.md retten — nur wenn diese noch fehlt und das alte doc-ids.md
# echte Datenzeilen im "## Projekt-Kürzel"-Abschnitt hat. Idempotent: existiert
# project-identifier.md schon, passiert nichts.
old_docids="$AGENT_DIR/doc-ids.md"
ident="$AGENT_DIR/project-identifier.md"
if [ ! -f "$ident" ] && [ -f "$old_docids" ]; then
  # Datenzeilen = |-Zeilen ab der dritten (nach Header + Separator) mit Alphanumerik
  kuerzel_rows="$(awk '
    /^## Projekt-K/ {insec=1; n=0; next}
    /^## / {insec=0}
    insec && /^\|/ { n++; if (n>2 && $0 ~ /[A-Za-z0-9]/) print }
  ' "$old_docids")"
  if [ -n "$kuerzel_rows" ]; then
    {
      cat <<'HDR'
# Projekt-Kürzel-Registry

Zentrale Registry der Projekt-Kürzel — **user-spezifischer State**, einmal pro
Agent/Maschine. Wird bei Konventions-Updates (`setup_global_tickets.sh`) **nie**
überschrieben.

Claude trägt beim ersten Einsatz von doc-ids oder Tickets in einem neuen Projekt das
Kürzel hier ein. Diese Datei ist die einzige Kürzel-Registry.

| Kürzel | Projekt |
|--------|---------|
HDR
      printf '%s\n' "$kuerzel_rows"
    } > "$ident"
    echo "  migrated: $ident (Kürzel aus altem doc-ids.md gerettet)"
  fi
fi

# doc-ids.md ist jetzt reine Konvention (Registry ausgelagert) → immer (neu) schreiben,
# damit Bestands-Agents Konventions-Updates bekommen.
dest="$AGENT_DIR/doc-ids.md"
if _fetch "docs/doc-ids.md" "$dest"; then
  echo "  deployed: $dest"
else
  exit 1
fi

# project-identifier.md enthält die Kürzel-Registry (User-State) → nur anlegen wenn
# fehlend (Migration oben kann sie bereits erzeugt haben), nie überschreiben.
dest="$AGENT_DIR/project-identifier.md"
if [ -f "$dest" ]; then
  echo "  $dest already exists — skipped (Kürzel-Registry bleibt erhalten)"
elif _fetch "docs/project-identifier.md" "$dest"; then
  echo "  deployed: $dest"
else
  exit 1
fi

# Bootstrap-Script bereitstellen, damit der unten gepatchte Hinweis
# "$AGENT_DIR/scripts/init_tickets.sh" auch wirklich existiert. Immer (neu)
# schreiben, damit Bestands-Agents die aktuelle Logik bekommen (idempotent).
mkdir -p "$AGENT_DIR/scripts"
if _fetch "scripts/init_tickets.sh" "$AGENT_DIR/scripts/init_tickets.sh"; then
  chmod +x "$AGENT_DIR/scripts/init_tickets.sh"
  echo "  deployed: $AGENT_DIR/scripts/init_tickets.sh"
else
  exit 1
fi

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
bash $AGENT_DIR/scripts/init_tickets.sh /pfad/zum/projekt
\`\`\`
BLOCK
    echo "  patched: $cfg (inline Ticketsystem block)"
  else
    echo "  $cfg already patched — skipped"
  fi
fi

echo "Done: $AGENT_DIR"
