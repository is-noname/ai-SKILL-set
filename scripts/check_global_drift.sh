#!/usr/bin/env bash
# Drift-Check für global deployte Konventionen/Artefakte (Inverse von
# setup_global_conventions.sh). Vergleicht die deployten Dateien in einem Agent-Dir
# gegen die Quelle im Repo und meldet pro Datei: ok / drift / missing. Prueft
# zusaetzlich, ob die repo-eigene tickets/PROTOCOL.md noch dem aktuellen
# scripts/ticket_protocol_template.md entspricht (IZG-T-091), und ob die DE/EN-
# Architektur-Docs dieselbe Abschnittsstruktur haben (IZG-T-096).
#
# Read-only — schreibt nie. Zum Re-Deploy: setup_global_conventions.sh <agent-dir>.
#
# Usage:
#   bash check_global_drift.sh                # alle bekannten Agent-Dirs unter $HOME
#   bash check_global_drift.sh ~/.claude      # nur ein Agent-Dir
#   bash check_global_drift.sh --all          # explizit alle (wie ohne Arg)
#
# Exit: 0 = alles aktuell, 1 = Drift/Fehlend gefunden, 2 = Aufruf-/Repo-Fehler.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Sourced statt dupliziert, damit render_*_block()/CFG_MAP nicht zweimal gepflegt
# werden muessen (IZG-T-100) — der Dispatcher-Teil von setup_global_conventions.sh
# ist per BASH_SOURCE-Guard geschuetzt und laeuft beim Sourcen nicht an.
# shellcheck source=setup_global_conventions.sh
source "$REPO_ROOT/scripts/setup_global_conventions.sh"

# project-identifier.md ist User-State → NICHT geprüft. Alles hier sind die von
# setup_global_conventions.sh stets überschriebenen (= managed) Dateien.
# Format: "<repo-relpath>|<agent-relpath>[|<nur-für-agent-dir>]"
# Das dritte Feld beschränkt den Eintrag auf ein Agent-Dir — für Dateien, die
# nur dort Sinn ergeben (die izg-decision-sheet-Hooks brauchen Claudes settings.json).
MANAGED=(
  "docs/tickets.md|tickets.md"
  "docs/doc-ids.md|doc-ids.md"
  "docs/design-tokens.md|design-tokens.md"
  "docs/file-reading.md|file-reading.md"
  "scripts/init_tickets.sh|scripts/init_tickets.sh"
  "scripts/ticket_protocol_template.md|scripts/ticket_protocol_template.md"
  "hooks/global/ticket-mover.sh|hooks/ticket-mover.sh"
  "skills/layer-1-base/izg-decision-sheet/hooks/izg-decision-answers.sh|hooks/izg-decision-answers.sh|.claude"
  "skills/layer-1-base/izg-decision-sheet/hooks/izg-decision-sheet-open.sh|hooks/izg-decision-sheet-open.sh|.claude"
)

KNOWN_AGENT_DIRS=(".claude" ".codex" ".gemini" ".vibe")

# Agent-Dirs bestimmen
agent_dirs=()
if [ "$#" -eq 0 ] || [ "$1" = "--all" ]; then
  for name in "${KNOWN_AGENT_DIRS[@]}"; do
    [ -d "$HOME/$name" ] && agent_dirs+=("$HOME/$name")
  done
  if [ "${#agent_dirs[@]}" -eq 0 ]; then
    echo "Keine bekannten Agent-Dirs unter $HOME gefunden (.claude/.codex/.gemini/.vibe)." >&2
    exit 2
  fi
else
  for arg in "$@"; do
    expanded="$(eval echo "$arg")"
    if [ ! -d "$expanded" ]; then
      echo "Error: $expanded existiert nicht." >&2
      exit 2
    fi
    agent_dirs+=("$expanded")
  done
fi

drift_found=0

# tickets/PROTOCOL.md dieses Repos ist selbst ein Bootstrap-Ergebnis von
# init_tickets.sh (Prefix IZG bereits eingesetzt) — kein global deploytes
# Artefakt, daher hier statt in MANAGED geprueft (IZG-T-091).
echo "== $REPO_ROOT/tickets/PROTOCOL.md vs. Template =="
rendered_template="$(sed 's/{PRJ}/IZG/g' "$REPO_ROOT/scripts/ticket_protocol_template.md")"
if [ "$rendered_template" = "$(cat "$REPO_ROOT/tickets/PROTOCOL.md")" ]; then
  echo "  ok tickets/PROTOCOL.md"
else
  echo "  !! tickets/PROTOCOL.md — DRIFT (weicht von scripts/ticket_protocol_template.md ab)"
  drift_found=1
fi

# DE/EN-Architektur-Docs muessen dieselbe Abschnittsstruktur haben (gleiche
# Ueberschriften ^##/^### in gleicher Reihenfolge/Anzahl) — kein Textvergleich,
# sonst schlaegt jede blosse Uebersetzung als Drift an (IZG-T-096).
echo "== docs/ticketsystem-architektur.md vs. docs/ticket-system-architecture.en.md =="
de_doc="$REPO_ROOT/docs/ticketsystem-architektur.md"
en_doc="$REPO_ROOT/docs/ticket-system-architecture.en.md"
if [ ! -f "$de_doc" ] || [ ! -f "$en_doc" ]; then
  echo "  ?? Architektur-Doc fehlt (DE oder EN)"
  drift_found=1
else
  # Nur die Ueberschriften-Ebene (##/###) je Zeile, kein Text — so bleibt reine
  # Uebersetzung unauffaellig, aber Reihenfolge/Anzahl/Ebene muessen matchen.
  de_pattern="$(grep -o '^#\{2,3\}' "$de_doc")"
  en_pattern="$(grep -o '^#\{2,3\}' "$en_doc")"
  de_headings="$(echo -n "$de_pattern" | grep -c '^#')"
  if [ "$de_pattern" = "$en_pattern" ]; then
    echo "  ok Abschnitts-Parität ($de_headings Überschriften je Seite, gleiche Reihenfolge)"
  else
    en_headings="$(echo -n "$en_pattern" | grep -c '^#')"
    echo "  !! Abschnitts-Parität — DRIFT (DE: $de_headings, EN: $en_headings Überschriften oder abweichende Reihenfolge)"
    drift_found=1
  fi
fi

# Prueft einen izg-block (IZG-T-100): vergleicht den Hash im Marker-Kommentar gegen
# den aus dem aktuellen Blockinhalt (render_*_block() aus setup_global_conventions.sh)
# berechneten Soll-Hash — dasselbe Format wie sync_block() beim Schreiben verwendet.
# Args: cfg, block_id, content, legacy_headings... (fuer die "unmarkiert"-Erkennung).
check_izg_block() {
  local cfg="$1" block_id="$2" content="$3"; shift 3
  local want_hash have_hash
  want_hash="$(printf '%s' "$content" | sha256sum | cut -d' ' -f1)"
  have_hash="$(grep -oE "izg-block:$block_id start hash:[0-9a-f]+" "$cfg" 2>/dev/null \
    | head -1 | sed -E 's/.*hash:([0-9a-f]+)/\1/')"

  if [ -n "$have_hash" ]; then
    if [ "$have_hash" = "$want_hash" ]; then
      echo "  ok izg-block:$block_id ($cfg)"
    else
      echo "  !! izg-block:$block_id ($cfg) — DRIFT (Hash im Marker weicht vom aktuellen Skript-Blockinhalt ab)"
      drift_found=1
    fi
    return
  fi

  local heading
  for heading in "$@"; do
    # Zeilenanfang-Match, identisch zu sync_block() (IZG-T-161).
    if awk -v h="$heading" 'index($0, h) == 1 { found = 1 } END { exit !found }' "$cfg"; then
      echo "  ~~ izg-block:$block_id ($cfg) — Sektion ohne Marker (vor IZG-T-092 angelegt oder von Hand ergaenzt, nicht automatisch pruefbar)"
      drift_found=1
      return
    fi
  done

  echo "  -- izg-block:$block_id ($cfg) — fehlt (nicht gepatcht)"
  drift_found=1
}

for adir in "${agent_dirs[@]}"; do
  echo "== $adir =="
  for entry in "${MANAGED[@]}"; do
    IFS='|' read -r src_rel rel only_dir <<< "$entry"
    # Eintrag ist auf ein Agent-Dir beschränkt und wir sind woanders → überspringen.
    [ -n "$only_dir" ] && [ "$(basename "$adir")" != "$only_dir" ] && continue
    src="$REPO_ROOT/$src_rel"
    dst="$adir/$rel"
    if [ ! -f "$src" ]; then
      echo "  ?? $rel — Repo-Quelle fehlt ($src_rel)"
      drift_found=1
    elif [ ! -f "$dst" ]; then
      echo "  -- $rel — fehlt (nicht deployt)"
      drift_found=1
    elif diff -q "$src" "$dst" >/dev/null 2>&1; then
      echo "  ok $rel"
    else
      echo "  !! $rel — DRIFT (deployt weicht ab)"
      drift_found=1
    fi
  done

  agent_name="$(basename "$adir")"
  cfg_file="${CFG_MAP[$agent_name]}"
  cfg="$adir/$cfg_file"
  if [ -z "$cfg_file" ]; then
    echo "  ?? unbekanntes Agent-Dir '$agent_name' — izg-block-Check übersprungen"
    drift_found=1
  elif [ ! -f "$cfg" ]; then
    echo "  ?? $cfg fehlt — izg-block-Check übersprungen"
    drift_found=1
  elif [ "$cfg_file" = "CLAUDE.md" ]; then
    check_izg_block "$cfg" "ticket-docid-design-tokens" "$(render_claude_ticket_block "$adir")" \
      "## Ticketsystem" "## Dokument-IDs" "## Design Tokens"
  else
    check_izg_block "$cfg" "ticket-lookup" "$(render_ticket_lookup_block "$adir")" "## Ticketsystem"
    check_izg_block "$cfg" "doc-ids-design-tokens" "$(render_doc_ids_design_tokens_block "$adir")" \
      "## Konventionen (Dokument-IDs & Design Tokens)"
  fi

  # Datei-Handling-Block: agent-unabhaengig (IZG-T-161).
  if [ -n "$cfg_file" ] && [ -f "$cfg" ]; then
    check_izg_block "$cfg" "file-reading" "$(render_file_reading_block "$adir")" "## Datei-Handling"
  fi
done

if [ "$drift_found" -ne 0 ]; then
  echo
  echo "Drift/Fehlend gefunden."
  echo "- Global deployte Dateien: bash $REPO_ROOT/scripts/setup_global_conventions.sh <agent-dir>"
  echo "- tickets/PROTOCOL.md dieses Repos: manuell an scripts/ticket_protocol_template.md angleichen (Prefix IZG)"
fi

exit "$drift_found"
