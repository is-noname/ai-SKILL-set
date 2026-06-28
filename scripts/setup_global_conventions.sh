#!/usr/bin/env bash
# Global setup/update for AI agent dirs. Deployt die Konventionen + Artefakte
# (tickets.md, doc-ids.md, init_tickets.sh, ticket-mover Hook) und patcht die
# Agent-Konfig. Idempotent — auch als Update auf Bestands-Agents anwendbar.
#
# Usage:
#   bash setup_global_conventions.sh ~/.vibe        # ein Agent-Dir
#   bash setup_global_conventions.sh ~/.claude ~/.codex   # mehrere
#   bash setup_global_conventions.sh --all          # alle bekannten Agent-Dirs unter $HOME
#   bash setup_global_conventions.sh                 # ohne Arg = --all
#
# Deployt das Konventions-Buendel (Tickets + doc-ids + project-identifier). NICHT zu
# verwechseln mit setup_global_hooks.sh (Guard-Hook-Deployer, andere Domaene).
# Alte Namen setup_global.sh und setup_global_tickets.sh existieren weiter als
# Alias-Wrapper (Rueckwaertskompatibilitaet).
#
# Agent dir → config file mapping:
#   ~/.claude  → CLAUDE.md
#   ~/.codex   → AGENTS.md   (Codex CLI >=0.x liest global AGENTS.md, nicht mehr instructions.md)
#   ~/.gemini  → GEMINI.md
#   ~/.vibe    → AGENTS.md

REPO_ROOT="$(dirname "$0")/.."

# RAW_BASE-Reihenfolge:
#   1. Env AISKILLSET_RAW_BASE (explizit überschreibbar)
#   2. aus dem git-Remote von REPO_ROOT abgeleitet (GitHub https/ssh)
#   3. hartkodierter Default als letzter Ausweg
# Greift nur, wenn der lokale docs/-Pfad fehlt (siehe _fetch).
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

declare -A CFG_MAP=(
  [".claude"]="CLAUDE.md"
  [".codex"]="AGENTS.md"
  [".gemini"]="GEMINI.md"
  [".vibe"]="AGENTS.md"
)
KNOWN_AGENT_DIRS=(".claude" ".codex" ".gemini" ".vibe")

# Holt eine Datei aus dem Repo: erst lokal aus REPO_ROOT/<relpath>, sonst via curl
# aus RAW_BASE/<relpath>. relpath ist repo-relativ (z.B. "docs/tickets.md").
_fetch() {
  local relpath="$1" dest="$2"
  local src="$REPO_ROOT/$relpath"
  if [ -f "$src" ]; then
    # Quelle und Ziel können dieselbe Datei sein (z.B. ~/.claude/scripts ist ins
    # Repo gelinkt) — cp meckert dann, ist aber bereits korrekt. Tolerieren.
    if [ "$src" -ef "$dest" ]; then
      return 0
    fi
    # Clobber-Schutz: ein existierendes Ziel, das inhaltlich abweicht UND neuer ist
    # als die Repo-Quelle, ist vermutlich eine lokale Anpassung (z.B. von Hand am
    # deployten Hook). Nicht überschreiben — Rückgabe 2 signalisiert "übersprungen".
    # Identische Dateien (cmp gleich) werden nie übersprungen, egal welche mtime.
    if [ -f "$dest" ] && ! cmp -s "$src" "$dest" && [ "$dest" -nt "$src" ]; then
      return 2
    fi
    cp "$src" "$dest"
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    local tmp="$dest.tmp.$$"
    if curl -fsSL "$RAW_BASE/$relpath" -o "$tmp"; then
      if [ -f "$dest" ] && ! cmp -s "$tmp" "$dest" && [ "$dest" -nt "$tmp" ]; then
        rm -f "$tmp"
        return 2
      fi
      mv "$tmp" "$dest"
      return 0
    fi
    rm -f "$tmp"  # curl legt bei Fehler ggf. eine leere Datei an
  fi
  echo "Error: '$relpath' konnte weder lokal ($src) noch via Remote" >&2
  echo "       ($RAW_BASE/$relpath) bezogen werden." >&2
  echo "       Repo lokal auschecken oder AISKILLSET_RAW_BASE auf eine erreichbare Quelle setzen." >&2
  return 1
}

# Wrapper um _fetch für die "immer (neu) schreiben"-Konventionsdateien: behandelt
# den Clobber-Schutz (Rückgabe 2) einheitlich. 0 = deployed ODER übersprungen
# (beides kein Fehler), 1 = echter Fehler.
deploy_file() {
  local relpath="$1" dest="$2"
  _fetch "$relpath" "$dest"
  local rc=$?
  case "$rc" in
    0) echo "  deployed: $dest" ;;
    2) echo "  WARNUNG: $dest ist lokal neuer als die Repo-Quelle ($relpath) und weicht ab — NICHT überschrieben (Clobber-Schutz). Lokale Änderung prüfen und ggf. nach $relpath ins Repo zurückführen, sonst geht sie beim nächsten echten Update verloren." >&2 ;;
    *) return 1 ;;
  esac
  return 0
}

# Setup/Update für genau ein Agent-Dir. Rückgabe 0 = ok, 1 = Fehler.
process_agent_dir() {
  local AGENT_DIR="$1"
  AGENT_DIR="$(eval echo "$AGENT_DIR")"  # expand ~ if passed as literal

  if [ ! -d "$AGENT_DIR" ]; then
    echo "Error: $AGENT_DIR does not exist." >&2
    return 1
  fi

  local agent_name cfg_file
  agent_name="$(basename "$AGENT_DIR")"
  cfg_file="${CFG_MAP[$agent_name]}"
  if [ -z "$cfg_file" ]; then
    echo "Unknown agent dir '$agent_name'. Supported: .claude .codex .gemini .vibe" >&2
    return 1
  fi

  echo "== $AGENT_DIR =="

  # tickets.md ist reine Konvention ohne user-spezifischen State → immer (neu)
  # schreiben, damit Bestands-Agents die aktuelle Version bekommen (idempotent).
  local dest="$AGENT_DIR/tickets.md"
  deploy_file "docs/tickets.md" "$dest" || return 1

  # Einmalige Migration: Älteres doc-ids.md trug die Kürzel-Registry inline. Bevor
  # wir doc-ids.md (jetzt reine Konvention) überschreiben, die Kürzel verlustfrei nach
  # project-identifier.md retten — nur wenn diese noch fehlt und das alte doc-ids.md
  # echte Datenzeilen im "## Projekt-Kürzel"-Abschnitt hat. Idempotent: existiert
  # project-identifier.md schon, passiert nichts.
  local old_docids="$AGENT_DIR/doc-ids.md"
  local ident="$AGENT_DIR/project-identifier.md"
  if [ ! -f "$ident" ] && [ -f "$old_docids" ]; then
    # Datenzeilen = |-Zeilen ab der dritten (nach Header + Separator) mit Alphanumerik
    local kuerzel_rows
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
Agent/Maschine. Wird bei Konventions-Updates (`setup_global_conventions.sh`) **nie**
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
  deploy_file "docs/doc-ids.md" "$dest" || return 1

  # project-identifier.md enthält die Kürzel-Registry (User-State) → nur anlegen wenn
  # fehlend (Migration oben kann sie bereits erzeugt haben), nie überschreiben.
  dest="$AGENT_DIR/project-identifier.md"
  if [ -f "$dest" ]; then
    echo "  $dest already exists — skipped (Kürzel-Registry bleibt erhalten)"
  elif _fetch "docs/project-identifier.md" "$dest"; then
    echo "  deployed: $dest"
  else
    return 1
  fi

  # Bootstrap-Script bereitstellen, damit der unten gepatchte Hinweis
  # "$AGENT_DIR/scripts/init_tickets.sh" auch wirklich existiert. Immer (neu)
  # schreiben, damit Bestands-Agents die aktuelle Logik bekommen (idempotent).
  mkdir -p "$AGENT_DIR/scripts"
  deploy_file "scripts/init_tickets.sh" "$AGENT_DIR/scripts/init_tickets.sh" || return 1
  [ -f "$AGENT_DIR/scripts/init_tickets.sh" ] && chmod +x "$AGENT_DIR/scripts/init_tickets.sh"

  # ticket-mover Hook bereitstellen — er ist das Kernversprechen der Konvention
  # ("Hook verschiebt die Datei automatisch", siehe tickets.md). Ohne ihn ist die
  # Status-Automatik tot. Immer (neu) schreiben (idempotent).
  mkdir -p "$AGENT_DIR/hooks"
  deploy_file "hooks/global/ticket-mover.sh" "$AGENT_DIR/hooks/ticket-mover.sh" || return 1
  [ -f "$AGENT_DIR/hooks/ticket-mover.sh" ] && chmod +x "$AGENT_DIR/hooks/ticket-mover.sh"

  # settings.json um den ticket-mover PostToolUse-Hook ergänzen — nur für Claude,
  # da dieses Hook-Format Claude-spezifisch ist. Idempotent: existiert der Eintrag
  # schon, passiert nichts. Fehlt settings.json, nur Hinweis (Hook liegt bereit).
  if [ "$agent_name" = ".claude" ]; then
    local settings="$AGENT_DIR/settings.json"
    if [ ! -f "$settings" ]; then
      echo "  $settings nicht gefunden — Hook nicht registriert (liegt bereit, manuell eintragen)"
    elif ! command -v python3 >/dev/null 2>&1; then
      echo "  python3 fehlt — settings.json nicht gepatcht (Hook liegt bereit, manuell eintragen)"
    else
      python3 - "$settings" "$AGENT_DIR/hooks/ticket-mover.sh" <<'PY'
import json, sys
settings_path, hook_cmd = sys.argv[1], sys.argv[2]
with open(settings_path) as f:
    data = json.load(f)
post = data.setdefault("hooks", {}).setdefault("PostToolUse", [])
already = any(
    h.get("command") == hook_cmd
    for entry in post
    for h in entry.get("hooks", [])
)
if already:
    print("  settings.json: ticket-mover bereits registriert — übersprungen")
    sys.exit(0)
post.insert(0, {
    "matcher": "Edit|Write",
    "hooks": [{
        "type": "command",
        "command": hook_cmd,
        "statusMessage": "Ticket-Status pruefen...",
    }],
})
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("  patched: settings.json (ticket-mover PostToolUse-Hook)")
PY
    fi
  fi

  local cfg="$AGENT_DIR/$cfg_file"
  if [ ! -f "$cfg" ]; then
    echo "  $cfg not found — skipping patch"
    return 0
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
  return 0
}

# --- Dispatcher: Ziel-Dirs bestimmen ---
target_dirs=()
if [ "$#" -eq 0 ] || [ "$1" = "--all" ]; then
  for name in "${KNOWN_AGENT_DIRS[@]}"; do
    [ -d "$HOME/$name" ] && target_dirs+=("$HOME/$name")
  done
  if [ "${#target_dirs[@]}" -eq 0 ]; then
    echo "Keine bekannten Agent-Dirs unter $HOME gefunden (.claude/.codex/.gemini/.vibe)." >&2
    exit 1
  fi
else
  target_dirs=("$@")
fi

rc=0
for d in "${target_dirs[@]}"; do
  process_agent_dir "$d" || rc=1
done
exit "$rc"
