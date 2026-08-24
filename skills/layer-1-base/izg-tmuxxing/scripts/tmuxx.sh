#!/usr/bin/env bash
# tmuxx - Worker-Agenten in tmux-Panes starten, fuettern, beobachten, beenden.
# Kapselt die verifizierten Fallen: pane_id statt Index, -x/-y bei detached,
# einzeiliger Prompt via Buffer, Text und Enter getrennt.
set -uo pipefail

STATE_DIR="${TMUXX_STATE_DIR:-$HOME/.tmuxx}"
mkdir -p "$STATE_DIR"

die() { echo "tmuxx: $*" >&2; exit 1; }

reg_file() { echo "$STATE_DIR/$1.state"; }

reg_load() {
  local f; f=$(reg_file "$1")
  [ -f "$f" ] || die "unbekannter Worker '$1' (siehe: tmuxx.sh list)"
  # shellcheck disable=SC1090
  . "$f"
  : "${SID:=}"
}

pane_alive() { tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -qx "$1"; }

# Claude Code fuehrt eine eigene Registry (kein TTY noetig): Name -> sessionId/status.
# Damit braucht es fuer Claude-Worker kein Spinner-Scraping.
claude_agent() { # <name> <feld>
  python3 -c '
import json, subprocess, sys
name, field = sys.argv[1], sys.argv[2]
try:
    out = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=15).stdout
    for a in json.loads(out):
        if a.get("name") == name:
            print(a.get(field, "")); break
except Exception:
    sys.exit(1)
' "$1" "$2" 2>/dev/null
}

# ---------------------------------------------------------------- start
cmd_start() {
  local name="" workdir="" worker="vibe" model="" split=0
  name="${1:?Name fehlt}"; shift
  workdir="${1:?Workdir fehlt}"; shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --worker) worker="$2"; shift 2 ;;
      --model)  model="$2";  shift 2 ;;
      --split)  split=1;     shift ;;
      *) die "unbekannte Option: $1" ;;
    esac
  done
  [[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || die "Name darf nur A-Z a-z 0-9 . _ - enthalten"
  [ -d "$workdir" ] || die "Workdir existiert nicht: $workdir"
  if [ -f "$(reg_file "$name")" ]; then
    ( reg_load "$name"; pane_alive "$PANE" ) && die "Worker '$name' laeuft schon"
  fi

  # tmux fuehrt das Kommando ueber eine Shell aus - alles Variable mit %q escapen.
  local cmd
  case "$worker" in
    vibe)
      [ -z "$model" ] || die "--model gibt es bei vibe nicht (Profil via --worker \"vibe ...\")"
      cmd=$(printf 'vibe --workdir %q --trust --agent auto-approve' "$workdir") ;;
    claude)
      cmd=$(printf 'claude --permission-mode acceptEdits -n %q' "$name")
      [ -z "$model" ] || cmd="$cmd $(printf -- '--model %q' "$model")" ;;
    *)  cmd="$worker" ;;
  esac

  local pane tsession
  if [ "$split" = 1 ]; then
    [ -n "${TMUX:-}" ] || die "--split braucht eine laufende tmux-Session"
    pane=$(tmux split-window -h -P -F '#{pane_id}' -c "$workdir" "$cmd") || die "split-window fehlgeschlagen"
    tsession=$(tmux display-message -p -t "$pane" '#{session_name}')
  else
    tsession="tmuxx-$name"
    tmux has-session -t "$tsession" 2>/dev/null && tmux kill-session -t "$tsession"
    pane=$(tmux new-session -d -s "$tsession" -x 200 -y 50 -c "$workdir" \
             -P -F '#{pane_id}' "$cmd") || die "new-session fehlgeschlagen"
  fi

  # Session-ID des Workers festnageln, solange sie eindeutig zuzuordnen ist -
  # Orchestrator und Worker teilen sich sonst denselben Transcript-Ordner.
  local sid=""
  if [ "$worker" = claude ]; then
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sid=$(claude_agent "$name" sessionId); [ -n "$sid" ] && break; sleep 1
    done
  fi

  # Die Registry wird von reg_load gesourced - Werte %q-quoten, nicht roh schreiben.
  printf 'NAME=%q\nPANE=%q\nTSESSION=%q\nWORKDIR=%q\nWORKER=%q\nSID=%q\nSTARTED=%q\n' \
    "$name" "$pane" "$tsession" "$workdir" "$worker" "$sid" "$(date -Iseconds)" \
    > "$(reg_file "$name")"
  echo "$pane"
}

# ---------------------------------------------------------------- send
# Prompt kommt von stdin oder als Argument. Newlines werden zu Leerzeichen:
# ein '\n' im Buffer sendet bei Vibe vorzeitig ab und verdoppelt Text.
cmd_send() {
  local name="${1:?Name fehlt}"; shift
  reg_load "$name"
  pane_alive "$PANE" || die "Pane $PANE ist weg - Worker '$name' laeuft nicht mehr"

  local text
  if [ $# -gt 0 ]; then text="$*"; else text=$(cat); fi
  [ -n "${text//[[:space:]]/}" ] || die "leerer Prompt"
  text=$(printf '%s' "$text" | tr '\n\r\t' '   ' | sed 's/  */ /g; s/^ //; s/ $//')

  local buf="tmuxx-$name"
  printf '%s' "$text" | tmux load-buffer -b "$buf" - || die "load-buffer fehlgeschlagen"
  tmux paste-buffer -b "$buf" -t "$PANE" -d || die "paste-buffer fehlgeschlagen"
  sleep 0.4

  # Ziel-Pane verifizieren, bevor Enter abschickt. Verglichen wird das ENDE des
  # Prompts (steht am Cursor, also immer sichtbar) und beides ohne Whitespace -
  # die TUI bricht den Text in ihrer Eingabebox hart um.
  local probe head
  head=$(printf '%s' "$text" | tr -d '[:space:]' | cut -c1-20)
  probe=$(tmux capture-pane -p -J -t "$PANE" | tail -25 | tr -d '[:space:]')
  if ! printf '%s' "$probe" | grep -qF "$head"; then
    die "Prompt steht nicht in $PANE (Dialog offen? falsches Pane?) - nichts abgeschickt.
     Achtung: der Text kann trotzdem in der Eingabebox stehen - mit 'tmuxx.sh peek $name'
     nachsehen und ggf. mit 'tmuxx.sh key $name C-c' verwerfen, bevor du neu sendest."
  fi
  tmux send-keys -t "$PANE" Enter
  echo "gesendet an $PANE (${#text} Zeichen)"
}

# ---------------------------------------------------------------- status / peek
cmd_status() {
  local name="${1:?Name fehlt}"
  reg_load "$name"
  if ! pane_alive "$PANE"; then echo "$name: dead"; return 1; fi
  local screen state="idle" reg=""
  [ "$WORKER" = claude ] && reg=$(claude_agent "$NAME" status)
  screen=$(tmux capture-pane -p -J -t "$PANE" | tail -25)
  # busy: Claude-Registry ist massgeblich, sonst Spinner ("Nucleating… (9s · …)",
  # Vibe "Generating…/Thinking…")
  if [ -n "$reg" ]; then
    [ "$reg" = busy ] && state="busy"
  else
    grep -qE '…\s*\([0-9]+s|Generating…|Thinking…|esc to interrupt' <<<"$screen" && state="busy"
  fi
  # dialog: blockierende Auswahl - hat Vorrang, der Worker kommt sonst nie weiter
  grep -qE 'Do you want|Allow once|trust this folder|\(y/n\)|❯\s*[0-9]\.' <<<"$screen" && state="dialog"
  echo "$name: $state  pane=$PANE worker=$WORKER workdir=$WORKDIR"
  [ "$state" = dialog ] && return 2
  [ "$state" = busy ] && return 3
  return 0
}

cmd_peek() {
  local name="${1:?Name fehlt}"; local n="${2:-30}"
  reg_load "$name"
  tmux capture-pane -p -J -t "$PANE" | tail -"$n"
}

cmd_key() {
  local name="${1:?Name fehlt}"; shift
  reg_load "$name"
  [ $# -gt 0 ] || die "keine Taste angegeben (z.B. Down, Enter, Escape, C-c)"
  for k in "$@"; do tmux send-keys -t "$PANE" "$k"; sleep 0.3; done
}

# ---------------------------------------------------------------- list / stop
cmd_list() {
  shopt -s nullglob
  local f
  for f in "$STATE_DIR"/*.state; do
    # shellcheck disable=SC1090
    ( . "$f"
      if pane_alive "$PANE"; then s=alive; else s=dead; fi
      printf '%-14s %-6s %-6s %-8s %s\n' "$NAME" "$PANE" "$WORKER" "$s" "$WORKDIR" )
  done
}

cmd_stop() {
  local name="${1:?Name fehlt}"
  reg_load "$name"
  if pane_alive "$PANE"; then
    tmux send-keys -t "$PANE" -l '/exit'; tmux send-keys -t "$PANE" Enter; sleep 2
  fi
  if pane_alive "$PANE"; then
    if [ "$TSESSION" = "tmuxx-$name" ]; then tmux kill-session -t "$TSESSION"
    else tmux kill-pane -t "$PANE"; fi
  fi
  rm -f "$(reg_file "$name")"
  echo "$name gestoppt"
}

# ---------------------------------------------------------------- cost
cmd_cost() {
  local name="${1:?Name fehlt}"
  reg_load "$name"
  python3 "$(dirname "$0")/worker_cost.py" --worker "$WORKER" --workdir "$WORKDIR" \
    --since "$STARTED" ${SID:+--session "$SID"}
}

case "${1:-}" in
  start)  shift; cmd_start  "$@" ;;
  send)   shift; cmd_send   "$@" ;;
  status) shift; cmd_status "$@" ;;
  peek)   shift; cmd_peek   "$@" ;;
  key)    shift; cmd_key    "$@" ;;
  list)   shift; cmd_list   "$@" ;;
  stop)   shift; cmd_stop   "$@" ;;
  cost)   shift; cmd_cost   "$@" ;;
  *) cat >&2 <<'USAGE'
tmuxx.sh start  <name> <workdir> [--worker vibe|claude|<cmd>] [--model sonnet] [--split]
tmuxx.sh send   <name> [prompt...]        # ohne Argument: Prompt von stdin
tmuxx.sh status <name>                    # idle|busy|dialog|dead (rc 0|3|2|1)
tmuxx.sh peek   <name> [zeilen]
tmuxx.sh key    <name> <taste...>         # z.B. Down Enter
tmuxx.sh list
tmuxx.sh cost   <name>
tmuxx.sh stop   <name>
USAGE
     exit 64 ;;
esac
