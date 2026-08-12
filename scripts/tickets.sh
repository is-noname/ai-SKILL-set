#!/usr/bin/env bash
# Schmales Abfrage-Interface fuer tickets/. Ersetzt Glob+Volltext-Read durch
# Frontmatter-Zeilen (list), gezielten Volltext-Read (show) und die bisherige
# next_ticket_id.sh-Logik (next). Siehe IZG-T-083.
# Verben: list, show, next, new, sync, move, help — Flags/Beispiele: tickets.sh help
# --- Inhaltsverzeichnis (auto) ---
# Von update_script_toc.py generiert — nicht von Hand pflegen.
#   cmd_list             Zeile 24
#   resolve_ticket_file  Zeile 98
#   cmd_show             Zeile 145
#   sync_one             Zeile 209
#   cmd_sync             Zeile 276
#   cmd_move             Zeile 305
#   cmd_next             Zeile 371
#   slugify              Zeile 407
#   cmd_new              Zeile 422
#   cmd_help             Zeile 535
# --- Ende Inhaltsverzeichnis ---

set -euo pipefail

TICKETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/tickets"

cmd_list() {
  local status_filter="" group_filter="" type_filter="" priority_filter=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --status) status_filter="$2"; shift 2 ;;
      --group) group_filter="$2"; shift 2 ;;
      --type) type_filter="$2"; shift 2 ;;
      --priority) priority_filter="$2"; shift 2 ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done

  local folders
  if [ -n "$status_filter" ]; then
    folders=("$status_filter")
  else
    folders=(in-progress open blocked)
  fi

  local folder file files=()
  for folder in "${folders[@]}"; do
    [ -d "$TICKETS_DIR/$folder" ] || continue
    # done/ ist nach Jahr unterteilt (IZG-T-084) - eine Ebene tiefer als die
    # aktiven Statusordner.
    if [ "$folder" = "done" ]; then
      for file in "$TICKETS_DIR/$folder"/*/*.md; do
        [ -e "$file" ] && files+=("$file")
      done
    else
      for file in "$TICKETS_DIR/$folder"/*.md; do
        [ -e "$file" ] && files+=("$file")
      done
    fi
  done
  [ ${#files[@]} -eq 0 ] && return 0

  # Ein awk-Durchlauf ueber alle Dateien statt frontmatter_field pro Feld/Datei
  # (IZG-T-090). FNR==1 resettet den Zustand pro Datei; nextfile bricht ab,
  # sobald das Frontmatter zuende ist oder ein Filter nicht passt.
  awk -v type_filter="$type_filter" -v group_filter="$group_filter" -v priority_filter="$priority_filter" '
    FNR == 1 { id = ""; type = ""; priority = ""; group = ""; infm = 0 }
    /^---$/ { infm++; next }
    infm == 1 {
      if ($0 ~ /^id: /)       { v = $0; sub(/^id: /, "", v);       id = v }
      else if ($0 ~ /^type: /)     { v = $0; sub(/^type: /, "", v);     type = v }
      else if ($0 ~ /^priority: /) { v = $0; sub(/^priority: /, "", v); priority = v }
      else if ($0 ~ /^group: /)    { v = $0; sub(/^group: /, "", v);    group = v }
      next
    }
    infm >= 2 {
      if (id == "") { nextfile }
      if (type_filter != "" && type != type_filter) { nextfile }
      if (group_filter != "" && group != group_filter) { nextfile }
      if (priority_filter != "" && priority != priority_filter) { nextfile }

      idx = index(FILENAME, "/tickets/")
      n = split(substr(FILENAME, idx + 9), parts, "/")
      folder = parts[1]
      slug = parts[n]
      sub(/\.md$/, "", slug)
      sub(/^[^_]*_/, "", slug)

      printf "%s\t%s\t%s\t%s\t%s\n", id, folder, type, priority, slug
      nextfile
    }
  ' "${files[@]}"
}

# Loest eine ID auf eine Ticketdatei auf: aktive Ordner (in-progress, open,
# blocked) zuerst, done/ (Jahresarchiv) nur als Fallback (IZG-T-095) - kein
# grep -r ueber ganz tickets/, das mit dem Archiv monoton waechst. Gemeinsam
# genutzt von cmd_show und cmd_move statt zweier Implementierungen. Gibt bei
# Erfolg genau einen Pfad auf stdout aus, bei keinem Treffer nichts. Mehrfache
# Treffer sind ein echter ID-Konflikt und brechen sofort ab.
resolve_ticket_file() {
  local id="$1"
  local folder file

  # Ordnerebene 1: aktive Statusordner in einem grep -l statt grep pro Datei.
  local -a active_files=()
  for folder in in-progress open blocked; do
    [ -d "$TICKETS_DIR/$folder" ] || continue
    for file in "$TICKETS_DIR/$folder"/*.md; do
      [ -e "$file" ] && active_files+=("$file")
    done
  done

  local -a matches=()
  if [ ${#active_files[@]} -gt 0 ]; then
    while IFS= read -r file; do
      matches+=("$file")
    done < <(grep -l "^id: ${id}\$" "${active_files[@]}" 2>/dev/null || true)
  fi

  # Ordnerebene 2: Jahresarchiv, nur als Fallback ohne Treffer oben.
  if [ ${#matches[@]} -eq 0 ] && [ -d "$TICKETS_DIR/done" ]; then
    local -a done_files=()
    for file in "$TICKETS_DIR/done"/*/*.md; do
      [ -e "$file" ] && done_files+=("$file")
    done
    if [ ${#done_files[@]} -gt 0 ]; then
      while IFS= read -r file; do
        matches+=("$file")
      done < <(grep -l "^id: ${id}\$" "${done_files[@]}" 2>/dev/null || true)
    fi
  fi

  [ ${#matches[@]} -eq 0 ] && return 0

  if [ ${#matches[@]} -gt 1 ]; then
    echo "Ticket mehrfach gefunden: $id" >&2
    printf '  %s\n' "${matches[@]}" >&2
    exit 1
  fi
  printf '%s\n' "${matches[0]}"
}

# Verlauf-Eintraege werden per Default auf die letzten zwei gekappt (IZG-T-095) -
# der Verlauf ist strukturell der am schnellsten wachsende Teil eines Tickets,
# wer nur wissen will was zu tun ist bezahlt sonst die volle Historie mit.
# --full liefert byteidentisch das bisherige Verhalten.
cmd_show() {
  local id="" full=0 brief=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --full) full=1; shift ;;
      --brief) brief=1; shift ;;
      -*) echo "Unbekannte Option: $1" >&2; exit 1 ;;
      *) id="$1"; shift ;;
    esac
  done
  if [ -z "$id" ]; then
    echo "Usage: tickets.sh show <ID> [--full|--brief]" >&2
    exit 1
  fi
  if [ "$full" -eq 1 ] && [ "$brief" -eq 1 ]; then
    echo "--full und --brief schliessen sich aus." >&2
    exit 1
  fi
  local match
  match="$(resolve_ticket_file "$id")"
  if [ -z "$match" ]; then
    echo "Ticket nicht gefunden: $id" >&2
    exit 1
  fi

  if [ "$brief" -eq 1 ]; then
    awk '/^## Verlauf/ { exit } { print }' "$match"
    return 0
  fi

  if [ "$full" -eq 1 ] || ! grep -q '^## Verlauf' "$match"; then
    cat "$match"
    return 0
  fi

  awk -v id="$id" '
    /^## Verlauf/ { in_verlauf = 1; print; next }
    in_verlauf && /^### / {
      n++
      buf[n] = $0
      next
    }
    in_verlauf {
      if (n == 0) { print; next }
      buf[n] = buf[n] "\n" $0
      next
    }
    { print }
    END {
      start = n - 1
      if (start < 1) start = 1
      for (i = start; i <= n; i++) print buf[i]
      if (n - 2 > 0) {
        printf "\n# %d weitere Verlaufseinträge — tickets.sh show %s --full\n", n - 2, id
      }
    }
  ' "$match"
}

# Verschiebt EINE Ticketdatei in den zu ihrem status:-Feld passenden Ordner
# (inkl. Jahresarchiv fuer done/, IZG-T-084). Idempotent: liegt die Datei schon
# richtig, passiert nichts. Gibt bei einer tatsaechlichen Aktion eine Zeile auf
# stdout aus, sonst keine. Kollisions- und Jahresarchiv-Logik lebt nur hier
# (IZG-T-088) — Claude- und Vibe-Hook-Adapter rufen ausschliesslich dies auf.
sync_one() {
  local file_path="$1"
  local result_var="${2:-}"
  [ -f "$file_path" ] || return 0
  [[ "$file_path" == */tickets/* ]] || return 0
  grep -qE "^id: [A-Z]+-T-[0-9]+" "$file_path" || return 0

  local status
  status="$(grep -m1 "^status: " "$file_path" | sed 's/^status: //' | tr -d '[:space:]"'"'"'')"
  [ -n "$status" ] || return 0
  case "$status" in
    open|in-progress|blocked|done) ;;
    *) return 0 ;;
  esac

  local current_dir current_folder filename target_dir tickets_root
  current_dir="$(dirname "$file_path")"
  current_folder="$(basename "$current_dir")"
  filename="$(basename "$file_path")"

  if [ "$status" = "done" ]; then
    local year
    year="$(grep -m1 "^created: " "$file_path" | sed 's/^created: //' | grep -oE "^[0-9]{4}" || true)"
    [ -n "$year" ] || year="$(date +%Y)"

    # done/ ist nach Jahr unterteilt: liegt die Datei schon in done/<jahr>/, ist
    # current_dir bereits tickets_root/done/<jahr> (zwei Ebenen ueber tickets_root).
    if [[ "$current_folder" =~ ^[0-9]{4}$ ]] && [ "$(basename "$(dirname "$current_dir")")" = "done" ]; then
      tickets_root="$(dirname "$(dirname "$current_dir")")"
    else
      tickets_root="$(dirname "$current_dir")"
    fi
    target_dir="$tickets_root/done/$year"
    if [ "$current_dir" = "$target_dir" ]; then
      [ -n "$result_var" ] && printf -v "$result_var" '%s' "$file_path"
      return 0
    fi
  else
    if [ "$current_folder" = "$status" ]; then
      [ -n "$result_var" ] && printf -v "$result_var" '%s' "$file_path"
      return 0
    fi
    tickets_root="$(dirname "$current_dir")"
    target_dir="$tickets_root/$status"
  fi

  mkdir -p "$target_dir"

  # Kollisionsschutz: nie ein vorhandenes Ziel ueberschreiben (z.B. gleiche ID in
  # zwei Ordnern durch fruehere manuelle Verschiebung).
  if [ -e "$target_dir/$filename" ]; then
    if cmp -s "$file_path" "$target_dir/$filename"; then
      rm -f "$file_path"
      echo "$filename: identische Dublette in $status/ gefunden — Quelle in $current_folder/ entfernt. Datei liegt jetzt unter $target_dir/."
      [ -n "$result_var" ] && printf -v "$result_var" '%s' "$target_dir/$filename"
      return 0
    fi
    echo "$filename: Ziel $status/ existiert bereits mit ABWEICHENDEM Inhalt — nicht verschoben (echter ID-Konflikt). Bitte manuell zusammenfuehren."
    [ -n "$result_var" ] && printf -v "$result_var" '%s' "$file_path"
    return 0
  fi

  mv -n "$file_path" "$target_dir/$filename"
  echo "$filename automatisch von $current_folder/ nach $status/ verschoben. Datei liegt jetzt unter $target_dir/ — kein manueller mv noetig."
  [ -n "$result_var" ] && printf -v "$result_var" '%s' "$target_dir/$filename"
}

cmd_sync() {
  local target="${1:-}"
  if [ -n "$target" ]; then
    sync_one "$target"
    return 0
  fi

  # Ohne Zielangabe: alle Ticketordner reconcilen (Codex/Gemini-Fallback ohne
  # Hook-Mechanik, siehe docs/tickets.md).
  local folder file
  for folder in open in-progress blocked; do
    [ -d "$TICKETS_DIR/$folder" ] || continue
    for file in "$TICKETS_DIR/$folder"/*.md; do
      [ -e "$file" ] || continue
      sync_one "$file"
    done
  done
  if [ -d "$TICKETS_DIR/done" ]; then
    for file in "$TICKETS_DIR/done"/*/*.md; do
      [ -e "$file" ] || continue
      sync_one "$file"
    done
  fi
  return 0
}

# Statuswechsel als ein Kommando statt Konventionsprosa (IZG-T-093): Verlaufseintrag
# anhaengen, status: setzen, sync_one aufrufen — unveraendert wiederverwendet fuer
# Kollisionsschutz und Jahresarchiv. Gibt bei Erfolg den neuen Pfad auf stdout aus.
cmd_move() {
  if [ $# -lt 3 ]; then
    echo "Usage: tickets.sh move <ID> <status> \"<verlaufstext>\" [--by <agent>]" >&2
    exit 1
  fi
  local id="$1" status="$2" note="$3"
  shift 3
  local by="claude"
  while [ $# -gt 0 ]; do
    case "$1" in
      --by) by="$2"; shift 2 ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done

  case "$status" in
    open|in-progress|blocked|done) ;;
    *) echo "Ungueltiger Status: $status (erlaubt: open|in-progress|blocked|done)" >&2; exit 1 ;;
  esac

  # Trim Whitespace, um "nur Leerzeichen" als leer zu behandeln.
  local note_trimmed="${note#"${note%%[![:space:]]*}"}"
  if [ -z "$note_trimmed" ]; then
    echo "Verlaufstext fehlt oder ist leer — Statuswechsel abgebrochen." >&2
    exit 1
  fi

  local file
  file="$(resolve_ticket_file "$id")"
  if [ -z "$file" ]; then
    echo "Ticket nicht gefunden: $id" >&2
    exit 1
  fi

  local current_status
  current_status="$(grep -m1 "^status: " "$file" | sed 's/^status: //' | tr -d '[:space:]"'"'"'')"

  if [ "$current_status" = "blocked" ] && [ "$status" = "in-progress" ]; then
    echo "Verbotener Uebergang blocked -> in-progress. Erst nach 'open' wechseln, dann nach 'in-progress'." >&2
    exit 1
  fi

  if grep -q '^## Verlauf' "$file"; then
    {
      echo ""
      echo "### $(date +%Y-%m-%d) – ${by}"
      echo "$note"
    } >> "$file"
  else
    {
      echo ""
      echo "## Verlauf"
      echo ""
      echo "### $(date +%Y-%m-%d) – ${by}"
      echo "$note"
    } >> "$file"
  fi

  sed -i "s/^status: .*/status: ${status}/" "$file"

  local target_path=""
  sync_one "$file" target_path

  printf '%s\n' "${target_path:-$file}"
}

cmd_next() {
  local PREFIX="${1:-PRJ}"
  local COUNTER_FILE="$TICKETS_DIR/.counter"

  if [ ! -d "$TICKETS_DIR" ]; then
    echo "Fehler: $TICKETS_DIR nicht gefunden. init_tickets.sh ausführen." >&2
    exit 1
  fi

  if command -v flock >/dev/null 2>&1; then
    exec 9>"$COUNTER_FILE.lock"
    flock 9
  fi

  local counter=0 c
  if [ -f "$COUNTER_FILE" ]; then
    c="$(tr -dc '0-9' < "$COUNTER_FILE")"
    [ -n "$c" ] && counter=$((10#$c))
  fi

  local max_existing
  max_existing="$(grep -rhoE "^id: ${PREFIX}-T-[0-9]+" "$TICKETS_DIR" 2>/dev/null \
    | grep -oE '[0-9]+$' | sort -n | tail -1 || true)"
  max_existing=$((10#${max_existing:-0}))

  local floor=$counter
  [ "$max_existing" -gt "$floor" ] && floor=$max_existing

  local next=$((floor + 1))
  echo "$next" > "$COUNTER_FILE"

  printf "%s-T-%03d\n" "$PREFIX" "$next"
}

# Kleinbuchstaben, Umlaute transliteriert, alles ausserhalb [a-z0-9] wird zu "-",
# Mehrfach-/Rand-Bindestriche entfernt, auf ~50 Zeichen gekuerzt (IZG-T-094).
slugify() {
  local s="$1"
  s="${s//Ä/Ae}"; s="${s//Ö/Oe}"; s="${s//Ü/Ue}"
  s="${s//ä/ae}"; s="${s//ö/oe}"; s="${s//ü/ue}"; s="${s//ß/ss}"
  s="$(printf '%s' "$s" | tr '[:upper:]' '[:lower:]')"
  s="$(printf '%s' "$s" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
  s="${s:0:50}"
  s="$(printf '%s' "$s" | sed -E 's/-+$//')"
  printf '%s' "$s"
}

# Ticketanlage als ein Kommando statt Frontmatter-Schema + Dateinamensschema aus
# docs/tickets.md im Agentenkontext (IZG-T-094). ID-Vergabe delegiert unveraendert
# an cmd_next (gleicher flock-Codepfad). Enum-Validierung laeuft VOR der ID-Vergabe,
# damit ein Abbruch keine ID verbraucht. Legt immer in open/ an.
cmd_new() {
  local type="" priority="" title="" group="" by="" assigned="" source="" body_arg="" ac_arg=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --type) type="$2"; shift 2 ;;
      --priority) priority="$2"; shift 2 ;;
      --title) title="$2"; shift 2 ;;
      --group) group="$2"; shift 2 ;;
      --by) by="$2"; shift 2 ;;
      --assigned) assigned="$2"; shift 2 ;;
      --source) source="$2"; shift 2 ;;
      --body) body_arg="$2"; shift 2 ;;
      --ac) ac_arg="$2"; shift 2 ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done
  if [ "$body_arg" = "-" ] && [ "$ac_arg" = "-" ]; then
    echo "--body und --ac koennen nicht beide von stdin lesen (--ac -)." >&2
    exit 1
  fi

  case "$type" in
    bug|task|feature|question) ;;
    *) echo "Ungueltiger Typ: '$type' (erlaubt: bug|task|feature|question)" >&2; exit 1 ;;
  esac
  case "$priority" in
    high|normal|low) ;;
    *) echo "Ungueltige Prioritaet: '$priority' (erlaubt: high|normal|low)" >&2; exit 1 ;;
  esac
  if [ -z "$title" ]; then
    echo "--title fehlt oder ist leer" >&2
    exit 1
  fi
  if [ -z "$by" ]; then
    echo "--by fehlt oder ist leer" >&2
    exit 1
  fi

  # Prefix aus tickets/PROTOCOL.md des Zielprojekts (dort von init_tickets.sh
  # verankert) — nicht aus der Registry, die ist agent-neutral und projektfremd.
  local prefix
  prefix="$(grep -oE '[A-Z]{2,6}-T-\{NNN\}' "$TICKETS_DIR/PROTOCOL.md" 2>/dev/null \
    | head -1 | sed -E 's/-T-\{NNN\}//')"
  if [ -z "$prefix" ]; then
    echo "Projekt-Prefix nicht ermittelbar aus tickets/PROTOCOL.md (Platzhalter {PRJ} noch nicht ersetzt?)." >&2
    echo "Erst: bash scripts/init_tickets.sh <pfad> PREFIX" >&2
    exit 1
  fi

  # Body erst NACH der Enum-/Prefix-Pruefung von stdin lesen — sonst haengt ein
  # ungueltiger Aufruf mit --body - am leeren stdin, bevor der eigentliche Fehler
  # gemeldet wird.
  local desc=""
  if [ "$body_arg" = "-" ]; then
    desc="$(cat)"
  elif [ -n "$body_arg" ]; then
    desc="$body_arg"
  fi

  local ac_raw=""
  if [ "$ac_arg" = "-" ]; then
    ac_raw="$(cat)"
  elif [ -n "$ac_arg" ]; then
    ac_raw="$ac_arg"
  fi

  local ac_block="- [ ] "
  if [ -n "$ac_raw" ]; then
    ac_block="$(printf '%s\n' "$ac_raw" | awk '{ if ($0 ~ /^- \[ \] /) print; else print "- [ ] " $0 }')"
  fi

  local id
  id="$(cmd_next "$prefix")"

  local slug filename filepath
  slug="$(slugify "$title")"
  filename="${id}_${slug}.md"
  mkdir -p "$TICKETS_DIR/open"
  filepath="$TICKETS_DIR/open/$filename"

  {
    echo "---"
    echo "id: $id"
    echo "title: $title"
    echo "type: $type"
    echo "status: open"
    echo "priority: $priority"
    echo "created: $(date +%F)"
    echo "created-by: $by"
    [ -n "$assigned" ] && echo "assigned: $assigned"
    [ -n "$group" ] && echo "group: $group"
    [ -n "$source" ] && echo "source: $source"
    echo "---"
    echo ""
    echo "## Beschreibung"
    echo ""
    [ -n "$desc" ] && echo "$desc"
    echo ""
    echo "## Akzeptanzkriterien"
    echo ""
    echo "$ac_block"
    echo ""
    echo "## Verlauf"
    echo ""
    echo "### $(date +%F) – ${by}"
    echo "Ticket erstellt."
  } > "$filepath"

  echo "$filepath"
}

# Einzige Quelle fuer Verben, Flags und Beispiele (IZG-T-102) — der Kopfkommentar
# verweist nur noch hierher, keine zweite Liste pflegen.
cmd_help() {
  cat <<'EOF'
tickets.sh <verb> [optionen]

  list   [--status open|in-progress|blocked|done] [--group SLUG] [--type TYPE]
         [--priority high|normal|low]
         Tickets auflisten. Ohne --status: in-progress, open, blocked.
         tickets.sh list --status done --priority high

  show   <ID> [--full|--brief]
         Ticketdatei anzeigen, Verlauf auf 2 Eintraege gekappt.
         --full: komplett. --brief: Frontmatter, Beschreibung, Akzeptanzkriterien
         ohne Verlauf. --full und --brief schliessen sich aus.
         tickets.sh show IZG-T-001 --brief

  next   <PREFIX>
         Naechste ID vergeben, ohne Ticket anzulegen.
         tickets.sh next IZG

  new    --type bug|task|feature|question --priority high|normal|low
         --title <TITLE> --by <AGENT>
         [--group SLUG] [--assigned AGENT] [--source DOC-ID] [--body TEXT|-]
         [--ac TEXT|-]
         Ticket anlegen, landet in open/. --body -: Beschreibung von stdin.
         --ac: Akzeptanzkriterien, mehrere Zeilen werden je ein "- [ ]"-Punkt.
         --ac -: von stdin. --body und --ac koennen nicht beide "-" sein.
         tickets.sh new --type task --priority high --title "Fix X" --by claude --ac "Kriterium 1
Kriterium 2"

  sync   [FILE]
         Ordner an status:-Feld angleichen. Ohne FILE: alle aktiven Ordner.
         tickets.sh sync tickets/open/IZG-T-001_x.md

  move   <ID> <status> "<verlaufstext>" [--by <agent>]
         Statuswechsel: Verlauf anhaengen, status setzen, Datei verschieben.
         Erlaubt: open|in-progress|blocked|done. blocked -> in-progress verboten,
         erst nach open.
         tickets.sh move IZG-T-001 in-progress "Angefangen" --by claude
EOF
}

case "${1:-}" in
  list) shift; cmd_list "$@" ;;
  show) shift; cmd_show "$@" ;;
  next) shift; cmd_next "$@" ;;
  new) shift; cmd_new "$@" ;;
  sync) shift; cmd_sync "$@" ;;
  move) shift; cmd_move "$@" ;;
  help) cmd_help ;;
  *)
    echo "Usage: tickets.sh {list|show|next|new|sync|move|help} — Details: tickets.sh help" >&2
    exit 1
    ;;
esac
