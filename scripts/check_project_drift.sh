#!/usr/bin/env bash
# Drift-Check fuer die PROJEKT-lokale Ticket-Infrastruktur (IZG-T-158). Gegenstueck
# zu check_global_drift.sh, das dieselbe Frage fuer die Agent-Dirs unter $HOME stellt.
#
# Hintergrund: pull_skill.py verteilt Skills. scripts/tickets.sh ist kein Skill,
# sondern Projekt-Infrastruktur — sie wird von init_tickets.sh deployt. Ohne einen
# Ist-Soll-Bericht driftet dieser Stand still ueber alle Projekte hinweg (in WDE
# fehlte tickets.sh ganz, ohne dass es je auffiel: der ticket-mover-Hook steigt
# wortlos aus, wenn <projekt>/scripts/tickets.sh fehlt).
#
# Geprueft wird pro Projekt:
#   - scripts/tickets.sh, next_ticket_id.sh, init_tickets.sh gegen die Repo-Quelle
#   - tickets/-Statusordner vollstaendig
#   - tickets/PROTOCOL.md vorhanden UND Prefix-Platzhalter ersetzt (sonst bricht
#     `tickets.sh new` mit "Projekt-Prefix nicht ermittelbar" ab)
#   - tickets/.counter konsistent (>= hoechste real vergebene ID)
#
# Read-only — schreibt nie. Zum Nachziehen: init_tickets.sh (idempotent).
#
# Usage:
#   bash check_project_drift.sh                       # alle Projekte unter den Suchwurzeln
#   bash check_project_drift.sh /pfad/zum/projekt ... # nur die genannten Projekte
#   IZG_PROJECT_ROOTS=~/Dokumente:~/src bash check_project_drift.sh
#
# Exit: 0 = alles aktuell, 1 = Drift/Fehlend gefunden, 2 = Aufruf-/Repo-Fehler.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Suchwurzeln fuer die Projektsuche. Ueberschreibbar per IZG_PROJECT_ROOTS
# (":"-getrennt), damit Projekte ausserhalb von ~/Dokumente mitgeprueft werden
# koennen, ohne das Skript zu aendern.
DEFAULT_ROOTS="$HOME/Dokumente"
SEARCH_DEPTH="${IZG_PROJECT_DEPTH:-5}"

# Von init_tickets.sh deployte Projekt-Skripte. Der Vergleich laeuft ueber den
# Dateiinhalt (cmp), nicht ueber eine Versionsnummer im Skript — siehe
# docs/ticketsystem-architektur.md, Abschnitt "Verteilung".
MANAGED_SCRIPTS=(tickets.sh next_ticket_id.sh init_tickets.sh)
STATUS_DIRS=(open in-progress blocked done)

drift_found=0

# Projekte finden: jedes Verzeichnis mit einem tickets/-Unterordner. .git und
# Abhaengigkeitsbaeume werden geprunt, sonst laeuft die Suche in node_modules leer.
discover_projects() {
  local roots="$1" root
  local IFS=':'
  for root in $roots; do
    root="$(eval echo "$root")"
    [ -d "$root" ] || continue
    find "$root" -maxdepth "$SEARCH_DEPTH" \
      -type d \( -name .git -o -name node_modules -o -name __pycache__ \
                 -o -name .venv -o -name venv \) -prune -o \
      -type d -name tickets -print 2>/dev/null
  done | sed 's#/tickets$##' | sort -u
}

# Hoechste real vergebene Ticketnummer im Projekt (alle Ordner inkl. done/-Archiv).
max_ticket_id() {
  local tdir="$1" prefix="$2"
  grep -rhoE "^id: ${prefix}-T-[0-9]+" "$tdir" 2>/dev/null \
    | grep -oE '[0-9]+$' | sort -n | tail -1
}

check_project() {
  local proj="$1"
  echo "== $proj =="

  local name src dst
  for name in "${MANAGED_SCRIPTS[@]}"; do
    src="$REPO_ROOT/scripts/$name"
    dst="$proj/scripts/$name"
    if [ ! -f "$src" ]; then
      echo "  ?? scripts/$name — Repo-Quelle fehlt"
      drift_found=1
    elif [ ! -f "$dst" ]; then
      echo "  -- scripts/$name — fehlt (nie deployt)"
      drift_found=1
    elif cmp -s "$src" "$dst"; then
      echo "  ok scripts/$name"
    else
      echo "  !! scripts/$name — VERALTET ($(wc -l < "$dst") Zeilen vs. $(wc -l < "$src") im Repo)"
      drift_found=1
    fi
  done

  local d missing_dirs=()
  for d in "${STATUS_DIRS[@]}"; do
    [ -d "$proj/tickets/$d" ] || missing_dirs+=("$d")
  done
  if [ "${#missing_dirs[@]}" -eq 0 ]; then
    echo "  ok tickets/ Statusordner vollstaendig"
  else
    echo "  -- tickets/ — Statusordner fehlen: ${missing_dirs[*]}"
    drift_found=1
  fi

  # PROTOCOL.md ist die projekt-lokale Prefix-Quelle fuer `tickets.sh new`.
  # Ein unersetzter {PRJ}-Platzhalter macht das Ticketsystem unbenutzbar, ohne
  # dass eine frisch kopierte tickets.sh das merkt.
  local protocol="$proj/tickets/PROTOCOL.md" prefix=""
  if [ ! -f "$protocol" ]; then
    echo "  -- tickets/PROTOCOL.md — fehlt"
    drift_found=1
  else
    prefix="$(grep -oE '[A-Z]{2,6}-T-\{NNN\}' "$protocol" 2>/dev/null \
      | head -1 | sed -E 's/-T-\{NNN\}//')"
    if [ -z "$prefix" ]; then
      echo "  !! tickets/PROTOCOL.md — Prefix-Platzhalter nicht ersetzt ('tickets.sh new' bricht ab)"
      drift_found=1
    else
      echo "  ok tickets/PROTOCOL.md (Prefix $prefix)"
    fi
  fi

  # Counter-Drift: .counter haelt die zuletzt vergebene Nummer. Liegt er unter der
  # hoechsten real vergebenen ID, wuerde `next` bestehende Tickets ueberschreiben.
  local counter_file="$proj/tickets/.counter"
  if [ -z "$prefix" ]; then
    echo "  ~~ tickets/.counter — nicht pruefbar (kein Prefix ermittelbar)"
  elif [ ! -f "$counter_file" ]; then
    echo "  -- tickets/.counter — fehlt"
    drift_found=1
  else
    local counter raw max
    raw="$(tr -dc '0-9' < "$counter_file")"
    if [ -z "$raw" ]; then
      echo "  !! tickets/.counter — kein gueltiger Zahlwert"
      drift_found=1
    else
      counter=$((10#$raw))
      max="$(max_ticket_id "$proj/tickets" "$prefix")"
      max=$((10#${max:-0}))
      if [ "$counter" -lt "$max" ]; then
        echo "  !! tickets/.counter — DRIFT (steht auf $counter, hoechste vergebene ID $prefix-T-$max)"
        echo "     Heilen: bash $proj/scripts/tickets.sh next $prefix --repair"
        drift_found=1
      else
        echo "  ok tickets/.counter ($counter)"
      fi
    fi
  fi
}

projects=()
if [ "$#" -gt 0 ] && [ "$1" != "--all" ]; then
  for arg in "$@"; do
    expanded="$(eval echo "$arg")"
    if [ ! -d "$expanded" ]; then
      echo "Error: $expanded existiert nicht." >&2
      exit 2
    fi
    projects+=("$(cd "$expanded" && pwd)")
  done
else
  while IFS= read -r p; do
    [ -n "$p" ] && projects+=("$p")
  done < <(discover_projects "${IZG_PROJECT_ROOTS:-$DEFAULT_ROOTS}")
  if [ "${#projects[@]}" -eq 0 ]; then
    echo "Keine Projekte mit tickets/-Ordner gefunden (Suchwurzeln: ${IZG_PROJECT_ROOTS:-$DEFAULT_ROOTS})." >&2
    exit 2
  fi
fi

for proj in "${projects[@]}"; do
  check_project "$proj"
done

if [ "$drift_found" -ne 0 ]; then
  echo
  echo "Drift/Fehlend gefunden."
  echo "- Skripte + Ordner nachziehen: bash $REPO_ROOT/scripts/init_tickets.sh <projekt> [PREFIX]"
  echo "  (idempotent; PREFIX ersetzt den {PRJ}-Platzhalter in tickets/PROTOCOL.md)"
  echo "- Counter heilen: bash <projekt>/scripts/tickets.sh next <PREFIX> --repair"
fi

exit "$drift_found"
