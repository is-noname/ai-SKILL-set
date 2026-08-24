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

# --- Inhaltsverzeichnis (auto) ---
# Von update_script_toc.py generiert — nicht von Hand pflegen.
#   _fetch                              Zeile 68
#   deploy_file                         Zeile 109
#   deploy_shared_convention            Zeile 126
#   deploy_decision_sheet               Zeile 151
#   sync_block                          Zeile 177
#   render_claude_ticket_block          Zeile 223
#   render_ticket_lookup_block          Zeile 250
#   render_doc_ids_design_tokens_block  Zeile 282
#   process_agent_dir                   Zeile 295
# --- Ende Inhaltsverzeichnis ---

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
  local relpath="$1" dest="$2" force="${3:-}"
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
    # force=1 überspringt den Schutz (für reine Konventions-Master: Repo gewinnt).
    if [ -z "$force" ] && [ -f "$dest" ] && ! cmp -s "$src" "$dest" && [ "$dest" -nt "$src" ]; then
      return 2
    fi
    cp "$src" "$dest"
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    local tmp="$dest.tmp.$$"
    if curl -fsSL "$RAW_BASE/$relpath" -o "$tmp"; then
      if [ -z "$force" ] && [ -f "$dest" ] && ! cmp -s "$tmp" "$dest" && [ "$dest" -nt "$tmp" ]; then
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

# Deployt eine reine Konventions-Datei als Single Source: eine physische Datei unter
# ~/ai-shared/, jeder Agent-Dir verweist per Symlink darauf (IZG-T-054, Muster aus
# T-045). Kein Kopier-Sync, keine Drift, kein Clobber-Schutz — bei reinen Konventionen
# gewinnt immer das Repo (im Gegensatz zu project-identifier.md = User-State).
# Args: relpath (repo-relativ), fname (Zielname), AGENT_DIR.
deploy_shared_convention() {
  local relpath="$1" fname="$2" AGENT_DIR="$3"
  local shared_dir="$HOME/ai-shared"
  local master="$shared_dir/$fname"
  local dest="$AGENT_DIR/$fname"
  mkdir -p "$shared_dir"

  # Master aus dem Repo aktualisieren — Repo gewinnt (force überspringt Clobber-Schutz).
  # Wird pro Agent-Dir aufgerufen, ist aber idempotent (schreibt denselben Inhalt).
  _fetch "$relpath" "$master" force || return 1

  # Agent-Dir auf den Master symlinken. Alte physische Kopie (reiner Repo-Inhalt)
  # gefahrlos ersetzen — sie enthält keinen User-State.
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$master" ]; then
    echo "  $dest already symlinked -> $master"
  else
    [ -e "$dest" ] && [ ! -L "$dest" ] && rm -f "$dest"
    ln -sf "$master" "$dest"
    echo "  symlinked: $dest -> $master"
  fi
}

# Deployt den izg-decision-sheet Renderer nach ~/ai-shared/izg-decision-sheet/ (IZG-T-063).
# Agent-neutral und bewusst NICHT pro Agent-Dir: der Skill referenziert den Pfad als
# Konvention, egal welcher Agent das Sheet schreibt. Idempotent.
deploy_decision_sheet() {
  local target="$HOME/ai-shared/izg-decision-sheet"
  local src="skills/layer-1-base/izg-decision-sheet"
  mkdir -p "$target"
  deploy_file "$src/assets/index.html" "$target/index.html" || return 1
  for py in sheet_spec.py sheet_state.py render_sheet.py fetch_answers.py resolve_answers.py; do
    deploy_file "$src/scripts/$py" "$target/$py" || return 1
    [ -f "$target/$py" ] && chmod +x "$target/$py"
  done
}

# Schreibt einen Block content-addressiert in $cfg (IZG-T-092): der Marker-Kommentar
# traegt einen Hash des Blockinhalts, statt nur "existiert irgendein Block" zu pruefen
# (das alte Verhalten liess Configs stillschweigend veralten, sobald sich der Block im
# Script aenderte — siehe IZG-T-087). Aendert sich der Inhalt eines bereits markierten
# Blocks, ersetzt sync_block ihn automatisch; ist er identisch, passiert nichts.
#
# Ein unmarkierter Alt-Block (vor diesem Marker-Schema angelegt oder von Hand ergaenzt,
# z.B. eigene Bullet-Points unter einer der Ueberschriften) wird NICHT automatisch
# entfernt/ersetzt — ein simpler Ueberschriften-Match kann echten User-Content nicht von
# reinem Script-Output unterscheiden und wuerde bei einer Abweichung Daten loeschen.
# Stattdessen: Hinweis ausgeben und ueberspringen; sobald der Block manuell auf das
# Marker-Format gehoben wurde, greift der Hash-Vergleich automatisch.
#
# Args: cfg, block_id, content, legacy_headings... (Ueberschriften, an denen ein
# unmarkierter Alt-Block erkannt und gemeldet wird — rein informativ).
sync_block() {
  local cfg="$1" block_id="$2" content="$3"; shift 3
  local hash
  hash="$(printf '%s' "$content" | sha256sum | cut -d' ' -f1)"
  local start_marker="<!-- izg-block:$block_id start hash:$hash -->"
  local start_prefix="<!-- izg-block:$block_id start hash:"
  local end_marker="<!-- izg-block:$block_id end -->"

  if grep -qF "$start_marker" "$cfg"; then
    echo "  $cfg: $block_id up to date — skipped"
    return 0
  fi

  if grep -qF "$start_prefix" "$cfg"; then
    local tmp="$cfg.tmp.$$"
    awk -v start="$start_prefix" -v end="$end_marker" '
      BEGIN { skip = 0 }
      index($0, start) == 1 { skip = 1; next }
      skip && $0 == end { skip = 0; next }
      !skip { print }
    ' "$cfg" > "$tmp"
    mv "$tmp" "$cfg"
    echo "  $cfg: $block_id changed upstream — replacing"
  else
    local heading
    for heading in "$@"; do
      if grep -qF "$heading" "$cfg"; then
        echo "  WARNUNG: $cfg enthält bereits eine \"$heading\"-Sektion ohne izg-block-Marker (vor IZG-T-092 angelegt oder von Hand angepasst) — NICHT automatisch verändert, um keine manuellen Ergänzungen zu verlieren. Block manuell mit dem aktuellen Skript-Inhalt abgleichen und in <!-- izg-block:$block_id start/end --> einfassen, danach übernimmt der Hash-Vergleich automatisch." >&2
        return 0
      fi
    done
  fi

  {
    echo ""
    echo "$start_marker"
    printf '%s\n' "$content"
    echo "$end_marker"
  } >> "$cfg"
  echo "  patched: $cfg ($block_id)"
}

# Block-Inhalte als eigene Funktionen statt inline in process_agent_dir (IZG-T-100):
# check_global_drift.sh sourced dieses Skript und ruft dieselben Funktionen auf, um den
# Soll-Hash zu berechnen — ein zweites Vorhalten des Blocktexts wuerde sonst lautlos
# aus dem Tritt geraten, sobald sich einer der beiden Orte aendert ohne den anderen.
render_claude_ticket_block() {
  local AGENT_DIR="$1"
  cat << BLOCK
## Ticketsystem

- Ticket anlegen: \`bash scripts/tickets.sh new --type ... --title "..." --by claude\`
  (Standardweg, ein Kommando statt ID abfragen + Datei von Hand anlegen).
- Status wechseln: \`bash scripts/tickets.sh move <ID> <status> "<verlaufstext>" --by claude\`
  (Standardweg). Alternativ das \`status:\`-Feld im Frontmatter direkt ändern — nie \`mv\`
  auf eine Ticketdatei, der \`ticket-mover\`-Hook verschiebt sie dann selbst.
- Jeder Statuswechsel braucht einen Verlaufseintrag.
- Tickets liegen in \`tickets/\`. Auf Ansage nachsehen — kein automatischer Scan bei Sessionstart.
- Voraussetzung: \`tickets/\` + \`scripts/tickets.sh\` im Repo-Root. Fehlen sie, ist das Projekt
  nicht gebootstrappt — dann kein Ticket von Hand mit erfundener ID anlegen, stattdessen
  Nutzer fragen (Bootstrap via \`init_tickets.sh\`?).
- Volle Konvention bei Bedarf lesen: \`$AGENT_DIR/tickets.md\`

## Dokument-IDs

Typ-Codes, ADR-Filter, Prefix-Registry bei Bedarf: \`$AGENT_DIR/doc-ids.md\`,
\`~/ai-shared/project-identifier.md\`

## Design Tokens

Farb-, Typo- und Komponentenwerte für UI-Arbeit: \`$AGENT_DIR/design-tokens.md\` — bei
Frontend-Aufgaben lesen. Nicht ungefragt anwenden: manche Projekte haben eine eigene
Palette, die ausdrücklich Vorrang hat.
BLOCK
}

render_ticket_lookup_block() {
  local AGENT_DIR="$1"
  local agent_name status_move_hint
  agent_name="$(basename "$AGENT_DIR")"
  if [ "$agent_name" = ".vibe" ]; then
    status_move_hint="Status-Feld im Frontmatter ändern — Hook verschiebt die Datei automatisch."
  else
    status_move_hint="Status-Feld im Frontmatter ändern, danach \`bash scripts/tickets.sh sync\` aufrufen — kein Hook verfügbar, die Datei wandert sonst nicht automatisch in den passenden Ordner."
  fi
  cat << BLOCK
## Ticketsystem

Vollständige Konvention: \`$AGENT_DIR/tickets.md\`

Lookup-Reihenfolge:
1. \`tickets/in-progress/\` — läuft noch was?
2. \`tickets/open/\` — nächste Arbeit
3. \`tickets/blocked/\` — nur wenn Blocker gezielt gelöst werden soll

Voraussetzung: \`tickets/\` + \`scripts/tickets.sh\` im Repo-Root. Fehlen sie, ist das Projekt
nicht gebootstrappt — dann kein Ticket von Hand mit erfundener ID anlegen, stattdessen
Nutzer fragen (Bootstrap via \`init_tickets.sh\`?).

Ticket anlegen: \`bash scripts/tickets.sh new --type ... --title "..." --by <agent>\`
(Standardweg, ein Kommando statt ID abfragen + Datei von Hand anlegen).
Status wechseln: \`bash scripts/tickets.sh move <ID> <status> "<verlaufstext>" --by <agent>\`
(Standardweg). Alternativ das \`status:\`-Feld direkt ändern: $status_move_hint

Neues Projekt bootstrappen (zweites Argument = Projekt-Prefix, optional — fehlt es,
bleibt der \`{PRJ}\`-Platzhalter in \`tickets/PROTOCOL.md\`):
\`\`\`bash
bash $AGENT_DIR/scripts/init_tickets.sh /pfad/zum/projekt PREFIX
\`\`\`
BLOCK
}

render_doc_ids_design_tokens_block() {
  local AGENT_DIR="$1"
  cat << BLOCK
## Konventionen (Dokument-IDs & Design Tokens)

Dokument-ID-Schema und Typ-Codes: \`$AGENT_DIR/doc-ids.md\`
Globale Design-Tokens (Farben, Typografie, Spacing) für Outputs/Reports: \`$AGENT_DIR/design-tokens.md\`

Beide sind Symlinks auf die gemeinsame Quelle \`~/ai-shared/\` — bei Bedarf lesen, nie über andere Agent-Dirs (z.B. \`~/.claude/\`) referenzieren.
BLOCK
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

  # tickets.md ist reine Konvention ohne user-spezifischen State → Single Source via
  # Symlink auf ~/ai-shared/ (IZG-T-054). Eine physische Datei, kein Kopier-Sync.
  local dest
  deploy_shared_convention "docs/tickets.md" "tickets.md" "$AGENT_DIR" || return 1

  # Einmalige Migration: Älteres doc-ids.md trug die Prefix-Registry inline. Bevor
  # wir doc-ids.md (jetzt reine Konvention) überschreiben, die Prefixe verlustfrei nach
  # project-identifier.md retten — nur wenn diese noch fehlt und das alte doc-ids.md
  # echte Datenzeilen im Registry-Abschnitt hat. Die Überschrift hiess historisch
  # "## Projekt-Kürzel", heute "## Projekt-Prefix" — der Matcher deckt beide ab.
  # Idempotent: existiert project-identifier.md schon, passiert nichts.
  local old_docids="$AGENT_DIR/doc-ids.md"
  local ident="$AGENT_DIR/project-identifier.md"
  if [ ! -f "$ident" ] && [ -f "$old_docids" ]; then
    # Datenzeilen = |-Zeilen ab der dritten (nach Header + Separator) mit Alphanumerik
    local prefix_rows
    prefix_rows="$(awk '
      /^## Projekt-(K|Pr)/ {insec=1; n=0; next}
      /^## / {insec=0}
      insec && /^\|/ { n++; if (n>2 && $0 ~ /[A-Za-z0-9]/) print }
    ' "$old_docids")"
    if [ -n "$prefix_rows" ]; then
      {
        cat <<'HDR'
# Projekt-Prefix-Registry

Zentrale Registry der Projekt-Prefixe — **user-spezifischer State**, einmal pro
Agent/Maschine. Wird bei Konventions-Updates (`setup_global_conventions.sh`) **nie**
überschrieben.

Claude trägt beim ersten Einsatz von doc-ids oder Tickets in einem neuen Projekt das
Prefix hier ein. Diese Datei ist die einzige Prefix-Registry.

| Prefix | Projekt |
|--------|---------|
HDR
        printf '%s\n' "$prefix_rows"
      } > "$ident"
      echo "  migrated: $ident (Prefix aus altem doc-ids.md gerettet)"
    fi
  fi

  # doc-ids.md ist jetzt reine Konvention (Registry ausgelagert) → Single Source via
  # Symlink auf ~/ai-shared/ (IZG-T-054).
  deploy_shared_convention "docs/doc-ids.md" "doc-ids.md" "$AGENT_DIR" || return 1

  # design-tokens.md — globale Designwerte, ebenfalls reine Konvention. Wird ab
  # IZG-T-054 erstmals an alle Agent-Dirs verteilt (lag zuvor nur in ~/.claude).
  deploy_shared_convention "docs/design-tokens.md" "design-tokens.md" "$AGENT_DIR" || return 1

  # project-identifier.md enthält die Prefix-Registry (User-State). Statt einer
  # Kopie pro Agent-Dir gibt es nur eine physische Datei unter ~/ai-shared/, jeder
  # Agent-Dir verweist per Symlink darauf (IZG-T-045) — kein Sync, keine Drift-Gefahr.
  local shared_dir="$HOME/ai-shared"
  local shared_ident="$shared_dir/project-identifier.md"
  dest="$AGENT_DIR/project-identifier.md"
  mkdir -p "$shared_dir"

  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$shared_ident" ]; then
    echo "  $dest already symlinked to $shared_ident — skipped"
  elif [ ! -e "$shared_ident" ]; then
    # Noch kein Shared-Master: vorhandene Kopie (Prefix-Registry mit echtem Inhalt)
    # als Master übernehmen statt sie zu verlieren; sonst frisches Template holen.
    if [ -f "$dest" ] && [ ! -L "$dest" ]; then
      mv "$dest" "$shared_ident"
      echo "  promoted: $dest -> $shared_ident (bestehende Registry wird Master)"
    elif ! _fetch "docs/project-identifier.md" "$shared_ident"; then
      return 1
    fi
    ln -s "$shared_ident" "$dest"
    echo "  symlinked: $dest -> $shared_ident"
  elif [ -f "$dest" ] && [ ! -L "$dest" ] && ! cmp -s "$dest" "$shared_ident"; then
    echo "  WARNUNG: $dest weicht vom Shared-Master ($shared_ident) ab — nicht automatisch überschrieben. Manuell abgleichen, dann erneut ausführen." >&2
  else
    [ -e "$dest" ] && [ ! -L "$dest" ] && rm -f "$dest"  # identische Alt-Kopie durch Symlink ersetzen
    ln -sf "$shared_ident" "$dest"
    echo "  symlinked: $dest -> $shared_ident"
  fi

  # Bootstrap-Script bereitstellen, damit der unten gepatchte Hinweis
  # "$AGENT_DIR/scripts/init_tickets.sh" auch wirklich existiert. Immer (neu)
  # schreiben, damit Bestands-Agents die aktuelle Logik bekommen (idempotent).
  mkdir -p "$AGENT_DIR/scripts"
  deploy_file "scripts/init_tickets.sh" "$AGENT_DIR/scripts/init_tickets.sh" || return 1
  [ -f "$AGENT_DIR/scripts/init_tickets.sh" ] && chmod +x "$AGENT_DIR/scripts/init_tickets.sh"
  # PROTOCOL.md-Vorlage: deployte init_tickets.sh braucht sie als Sibling (IZG-T-091).
  deploy_file "scripts/ticket_protocol_template.md" "$AGENT_DIR/scripts/ticket_protocol_template.md" || return 1

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

  # Vibe-Adapter fuer denselben ticket-mover (IZG-T-088): Vibe hat kein
  # Claude-settings.json-Format, sondern hooks.toml mit [[hooks]]-Eintraegen
  # (Typ post_tool). Datei bereitstellen + in hooks.toml registrieren.
  if [ "$agent_name" = ".vibe" ]; then
    mkdir -p "$AGENT_DIR/hooks"
    deploy_file "hooks/global/ticket-mover-vibe.sh" "$AGENT_DIR/hooks/ticket-mover-vibe.sh" || return 1
    [ -f "$AGENT_DIR/hooks/ticket-mover-vibe.sh" ] && chmod +x "$AGENT_DIR/hooks/ticket-mover-vibe.sh"

    local vibe_hook_cmd="$AGENT_DIR/hooks/ticket-mover-vibe.sh"
    local vibe_hooks_toml="$AGENT_DIR/hooks.toml"
    if [ ! -f "$vibe_hooks_toml" ]; then
      cat > "$vibe_hooks_toml" << TOML
[[hooks]]
name = "ticket-mover"
type = "post_tool"
command = "$vibe_hook_cmd"
description = "Ticket-Status pruefen und Datei bei Bedarf verschieben (tickets.sh sync)"
TOML
      echo "  created: $vibe_hooks_toml (ticket-mover post_tool-Hook)"
    elif grep -qF "$vibe_hook_cmd" "$vibe_hooks_toml"; then
      echo "  $vibe_hooks_toml: ticket-mover bereits registriert — uebersprungen"
    else
      {
        echo ""
        echo "[[hooks]]"
        echo "name = \"ticket-mover\""
        echo "type = \"post_tool\""
        echo "command = \"$vibe_hook_cmd\""
        echo "description = \"Ticket-Status pruefen und Datei bei Bedarf verschieben (tickets.sh sync)\""
      } >> "$vibe_hooks_toml"
      echo "  patched: $vibe_hooks_toml (ticket-mover post_tool-Hook)"
    fi
  fi

  # izg-decision-sheet (IZG-T-063): Renderer global bereitstellen, Abhol-Hook je Agent-Dir.
  deploy_decision_sheet || return 1
  # Quelle sind die Hooks IM Skill, nicht hooks/global/: so kommen sie beim
  # Skill-Pull mit und lassen sich auch ohne dieses Repo einrichten.
  # Nur nach .claude: die Hooks setzen Claudes settings.json-Format voraus und
  # wuerden in den anderen Agent-Dirs nur unregistriert herumliegen.
  if [ "$agent_name" = ".claude" ]; then
    for ds_hook in izg-decision-answers.sh izg-decision-sheet-open.sh; do
      deploy_file "skills/layer-1-base/izg-decision-sheet/hooks/$ds_hook" "$AGENT_DIR/hooks/$ds_hook" || return 1
      [ -f "$AGENT_DIR/hooks/$ds_hook" ] && chmod +x "$AGENT_DIR/hooks/$ds_hook"
    done
  fi

  # Beide Hooks registrieren — Claude-spezifisches settings.json-Format:
  #   UserPromptSubmit → #answers holt Antworten ab
  #   Stop             → fertig geschriebenes Sheet geht automatisch auf
  if [ "$agent_name" = ".claude" ]; then
    local ds_settings="$AGENT_DIR/settings.json"
    if [ ! -f "$ds_settings" ]; then
      echo "  $ds_settings nicht gefunden — izg-decision-sheet-Hooks nicht registriert (liegen bereit)"
    elif ! command -v python3 >/dev/null 2>&1; then
      echo "  python3 fehlt — izg-decision-sheet-Hooks nicht registriert (liegen bereit)"
    else
      python3 - "$ds_settings" "$AGENT_DIR/hooks" <<'PY'
import json, sys
settings_path, hooks_dir = sys.argv[1], sys.argv[2]
with open(settings_path) as f:
    data = json.load(f)
hooks = data.setdefault("hooks", {})
wanted = [
    ("UserPromptSubmit", f"{hooks_dir}/izg-decision-answers.sh", "Decision-Sheet-Antworten pruefen..."),
    ("Stop", f"{hooks_dir}/izg-decision-sheet-open.sh", "Decision Sheet oeffnen..."),
]
changed = []
for event, cmd, msg in wanted:
    entries = hooks.setdefault(event, [])
    if any(h.get("command") == cmd for e in entries for h in e.get("hooks", [])):
        continue
    entries.append({"hooks": [{"type": "command", "command": cmd, "statusMessage": msg}]})
    changed.append(event)
if not changed:
    print("  settings.json: izg-decision-sheet-Hooks bereits registriert — übersprungen")
    sys.exit(0)
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("  patched: settings.json (izg-decision-sheet: " + ", ".join(changed) + ")")
PY
    fi
  fi

  local cfg="$AGENT_DIR/$cfg_file"
  if [ ! -f "$cfg" ]; then
    echo "  $cfg not found — skipping patch"
    return 0
  fi

  if [ "$cfg_file" = "CLAUDE.md" ]; then
    # Inline-Block mit Pfadverweisen statt @-Includes (IZG-T-081) — kein Auto-Scan-Satz,
    # Lookup reaktiv formuliert. Content-addressiert (IZG-T-092): sync_block ersetzt den
    # Block automatisch, sobald sich sein Inhalt hier im Script aendert.
    local claude_block
    claude_block="$(render_claude_ticket_block "$AGENT_DIR")"
    sync_block "$cfg" "ticket-docid-design-tokens" "$claude_block" \
      "## Ticketsystem" "## Dokument-IDs" "## Design Tokens"
    if grep -qE "^@(tickets|doc-ids|design-tokens)\.md" "$cfg"; then
      echo "  Hinweis: $cfg enthält noch alte @-Includes (@tickets.md/@doc-ids.md/@design-tokens.md) — Script fasst sie nicht an, manuell entfernen."
    fi
  else
    # Vibe hat einen registrierten post_tool-Hook (ticket-mover-vibe.sh, s.o.) —
    # Codex/Gemini haben keine Hook-Mechanik und muessen tickets.sh sync selbst
    # aufrufen (IZG-T-088).
    local ticket_block
    ticket_block="$(render_ticket_lookup_block "$AGENT_DIR")"
    sync_block "$cfg" "ticket-lookup" "$ticket_block" "## Ticketsystem"

    # doc-ids.md + design-tokens.md als Prosa-Verweis auf den LOKALEN (symgelinkten)
    # Pfad — nie über andere Agent-Dirs.
    local conventions_block
    conventions_block="$(render_doc_ids_design_tokens_block "$AGENT_DIR")"
    sync_block "$cfg" "doc-ids-design-tokens" "$conventions_block" "## Konventionen (Dokument-IDs & Design Tokens)"
  fi

  echo "Done: $AGENT_DIR"
  return 0
}

# Dispatcher nur ausfuehren, wenn das Skript direkt aufgerufen wird — check_global_drift.sh
# sourced diese Datei, um render_*_block()/CFG_MAP wiederzuverwenden, ohne dabei einen
# echten Deploy anzustossen (IZG-T-100).
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then

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

fi
