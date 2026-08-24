#!/usr/bin/env bash
# tmuxx - Worker-Agenten in tmux-Panes starten, fuettern, beobachten, beenden.
# Kapselt die verifizierten Fallen: pane_id statt Index, -x/-y bei detached,
# einzeiliger Prompt via Buffer, Text und Enter getrennt.
set -uo pipefail

STATE_DIR="${TMUXX_STATE_DIR:-$HOME/.tmuxx}"
mkdir -p "$STATE_DIR"

die() { echo "tmuxx: $*" >&2; exit 1; }

# Zwei Spinner-Muster, und die Unterscheidung ist der ganze Punkt:
#
# LIVE - laeuft der Worker JETZT. Claude laesst die fertige Spinnerzeile
# ("✻ Brewed for 4s") im Transcript stehen; nur solange wirklich gearbeitet wird,
# haengt "esc to interrupt" daran. Wer auf die Spinnerzeile allein prueft, haelt
# einen fertigen Worker fuer ewig busy.
SPINNER_LIVE_RE='esc to interrupt|Generating…|Thinking…|…[[:space:]]*\([0-9]+s'
# ANY - Spinnerzeilen jeder Art, auch abgelaufene. Nur zum Filtern von Auszuegen.
SPINNER_ANY_RE='^[[:space:]]*[^[:alnum:][:space:]][[:space:]]+[A-Za-z]+([[:space:]]+for)?[[:space:]]+[0-9]+s([[:space:]]|$)'
SPINNER_ANY_RE="$SPINNER_ANY_RE|$SPINNER_LIVE_RE"

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
  local name="" workdir="" worker="vibe" model="" split=0 inpane=""
  name="${1:?Name fehlt}"; shift
  workdir="${1:?Workdir fehlt}"; shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --worker) worker="$2"; shift 2 ;;
      --model)  model="$2";  shift 2 ;;
      --pane)   inpane="$2"; shift 2 ;;
      --split)  split=1;     shift ;;
      *) die "unbekannte Option: $1" ;;
    esac
  done
  [ -z "$inpane" ] || [ "$split" = 0 ] || die "--pane und --split schliessen sich aus"
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
  if [ -n "$inpane" ]; then
    # Ein bereits offenes Pane des Nutzers uebernehmen, statt sein Layout zu zerschneiden.
    pane_alive "$inpane" || die "Pane '$inpane' gibt es nicht (siehe: tmux list-panes -a)"
    local cur; cur=$(tmux display-message -p -t "$inpane" '#{pane_current_command}')
    case "$cur" in
      bash|zsh|sh|fish) : ;;
      *) die "in $inpane laeuft '$cur' - nur eine leere Shell wird uebernommen" ;;
    esac
    tmux respawn-pane -k -t "$inpane" -c "$workdir" "$cmd" || die "respawn-pane fehlgeschlagen"
    pane="$inpane"
    tsession=$(tmux display-message -p -t "$pane" '#{session_name}')
  elif [ "$split" = 1 ]; then
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
  printf 'NAME=%q\nPANE=%q\nTSESSION=%q\nWORKDIR=%q\nWORKER=%q\nSID=%q\nSTARTED=%q\nADOPTED=%q\n' \
    "$name" "$pane" "$tsession" "$workdir" "$worker" "$sid" "$(date -Iseconds)" \
    "$([ -n "$inpane" ] && echo 1 || echo 0)" \
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
# Optionszeilen einer blockierenden Auswahl ("❯ 1. Yes", "2. Yes, for this session").
dialog_opts() {
  grep -E '^[[:space:]]*[│|]?[[:space:]]*[❯>]?[[:space:]]*[0-9]+\.[[:space:]]' \
    | sed 's/^[[:space:]]*[│|]\?[[:space:]]*//; s/[[:space:]]*[│|]\?[[:space:]]*$//'
}

# Rahmen, Blockgrafik, Trennlinien und TUI-Fusszeilen weg - der Rest ist Signal.
# Kriterium: eine Zeile mit weniger als 4 alphanumerischen Zeichen traegt keine
# Information, egal wie viel Rahmen drumherum steht.
signal_lines() {
  sed 's/^[[:space:]]*[│|][[:space:]]*//; s/[[:space:]]*[│|][[:space:]]*$//' \
    | grep -vE '\? for shortcuts|esc to interrupt|ctrl\+[a-z]|shift\+tab|· /[a-z]+|accept edits on' \
    | grep -vE '^[[:space:]]*[─═]{5,}' \
    | grep -vE '[▐▛▜▝▘▗▖█▀▄]{2,}' \
    | grep -vE "$SPINNER_ANY_RE" \
    | grep -vE '@[[:alnum:].-]+:.*(Sonnet|Opus|Haiku|Fable)[[:space:]]*[0-9]?[[:space:]]*\|' \
    | awk '{ n = gsub(/[A-Za-z0-9]/, "&"); if (n >= 4) print }' \
    | cat -s
}

# Setzt STATE und SCREEN. Einzige Zustandsquelle - status, answer und await teilen sie,
# damit "busy" ueberall dasselbe heisst.
probe() {
  if ! pane_alive "$PANE"; then STATE=dead; SCREEN=""; return; fi
  local reg=""
  STATE=idle
  [ "$WORKER" = claude ] && reg=$(claude_agent "$NAME" status)
  SCREEN=$(tmux capture-pane -p -J -t "$PANE" | tail -25)
  # busy: Registry ODER Spinner. Die Claude-Registry flippt nach einem send erst
  # mit Verzoegerung auf busy - wer ihr allein glaubt, meldet in genau dieser
  # Luecke faelschlich idle. Ein falsches busy kostet nur Wartezeit, ein falsches
  # idle kostet ein verworfenes Ergebnis.
  if [ "$reg" = busy ] || grep -qE "$SPINNER_LIVE_RE" <<<"$SCREEN"; then
    STATE=busy
  fi
  # dialog: blockierende Auswahl - hat Vorrang, der Worker kommt sonst nie weiter
  grep -qE 'Do you want|Allow once|trust this folder|\(y/n\)|❯\s*[0-9]\.' <<<"$SCREEN" && STATE=dialog
}

rc_for_state() {
  case "$1" in dead) return 1 ;; dialog) return 2 ;; busy) return 3 ;; *) return 0 ;; esac
}

# Bei dialog haengen die Optionen immer an - sonst kostet jedes Ja/Nein ein extra
# peek. Der idle-Auszug kostet Tokens und lohnt nur nach einem Lauf, also nur in
# await (arg 1 = mit Auszug), nicht im blossen status.
report_state() {
  echo "$NAME: $STATE  pane=$PANE worker=$WORKER workdir=$WORKDIR"
  case "$STATE" in
    dialog) dialog_opts <<<"$SCREEN" | sed 's/^/  /' ;;
    idle)   [ "${1:-0}" = 1 ] && printf '%s\n' "$SCREEN" | signal_lines | tail -5 | sed 's/^/  /' ;;
  esac
  return 0
}

cmd_status() {
  local name="${1:?Name fehlt}"
  reg_load "$name"
  local STATE SCREEN
  probe
  report_state
  rc_for_state "$STATE"
}

# ---------------------------------------------------------------- answer
# Beantwortet eine blockierende Auswahl in EINEM Aufruf: Optionen lesen, von der
# aktuell markierten Zeile aus navigieren, Enter. Default 2 = "remainder of this
# session" - nie Option 3/"Always allow", das aendert die Config des Nutzers.
cmd_answer() {
  local name="${1:?Name fehlt}"; local target="${2:-2}"
  [[ "$target" =~ ^[0-9]+$ ]] || die "Option muss eine Zahl sein (bekommen: '$target')"
  reg_load "$name"
  local STATE SCREEN
  probe
  [ "$STATE" = dialog ] || die "'$name' steht nicht in einem Dialog (Zustand: $STATE) - nichts gedrueckt"

  local opts cur=1 n=0 i=0 line
  opts=$(dialog_opts <<<"$SCREEN")
  [ -n "$opts" ] || die "Dialog erkannt, aber keine nummerierten Optionen lesbar - mit 'peek $name' nachsehen"
  while IFS= read -r line; do
    i=$((i + 1)); n=$i
    [[ "$line" =~ ^[❯\>] ]] && cur=$i
  done <<<"$opts"
  [ "$target" -ge 1 ] && [ "$target" -le "$n" ] || die "Option $target gibt es nicht (Dialog hat $n)"

  local delta=$((target - cur)) key=Down
  [ "$delta" -lt 0 ] && { key=Up; delta=$((-delta)); }
  while [ "$delta" -gt 0 ]; do tmux send-keys -t "$PANE" "$key"; sleep 0.2; delta=$((delta - 1)); done
  tmux send-keys -t "$PANE" Enter
  sleep 0.6

  probe
  echo "$name: Option $target gewaehlt -> $STATE"
  [ "$STATE" = dialog ] && echo "  Achtung: immer noch ein Dialog offen (Folgedialog?) - erneut answer"
  return 0
}

# ---------------------------------------------------------------- await
# Wartet INNERHALB des Prozesses, statt den Orchestrator pro Check einen Turn
# kosten zu lassen. Kehrt bei idle, dialog, dead oder Timeout zurueck.
cmd_await() {
  local name="${1:?Name fehlt}"; local timeout="${2:-120}"
  [[ "$timeout" =~ ^[0-9]+$ ]] || die "Timeout muss Sekunden als Zahl sein (bekommen: '$timeout')"
  reg_load "$name"
  # idle muss sich BESTAETIGEN: direkt nach einem send hat der Worker noch nicht
  # angefangen und saehe idle aus. dialog und dead gelten dagegen sofort.
  local STATE SCREEN waited=0 iv=1 idle_ok=0 settle=3
  while :; do
    probe
    case "$STATE" in
      busy)      idle_ok=0 ;;
      idle)      idle_ok=$((idle_ok + 1)); [ "$idle_ok" -ge "$settle" ] && break ;;
      *)         break ;;
    esac
    [ "$waited" -ge "$timeout" ] && { echo "$name: timeout nach ${timeout}s (Zustand: $STATE)"; return 4; }
    sleep "$iv"; waited=$((waited + iv))
    # Abstand wachsen lassen: kurze Laeufe schnell erkennen, lange nicht dauerpollen.
    [ "$waited" -ge 10 ] && iv=2
    [ "$waited" -ge 60 ] && iv=5
  done
  report_state 1
  echo "  (nach ${waited}s)"
  rc_for_state "$STATE"
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
  if [ "${ADOPTED:-0}" = 1 ]; then
    # Uebernommenes Pane gehoert dem Nutzer - Shell zurueckgeben, nicht schliessen.
    # Kein '/exit' vorweg: der Worker beendet sich, das Pane stirbt mit, und das
    # Pane des Nutzers ist weg, bevor respawn es zurueckgeben kann.
    # Shell explizit nennen: respawn-pane ohne Kommando startet das URSPRUENGLICHE
    # Kommando des Panes neu - also den Worker, den wir gerade beenden wollen.
    pane_alive "$PANE" && { tmux respawn-pane -k -t "$PANE" -c "$WORKDIR" "${SHELL:-/bin/bash}" \
        || die "respawn-pane fehlgeschlagen"; }
  else
    if pane_alive "$PANE"; then
      tmux send-keys -t "$PANE" -l '/exit'; tmux send-keys -t "$PANE" Enter; sleep 2
    fi
    if pane_alive "$PANE"; then
      if [ "$TSESSION" = "tmuxx-$name" ]; then tmux kill-session -t "$TSESSION"
      else tmux kill-pane -t "$PANE"; fi
    fi
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
  await)  shift; cmd_await  "$@" ;;
  answer) shift; cmd_answer "$@" ;;
  peek)   shift; cmd_peek   "$@" ;;
  key)    shift; cmd_key    "$@" ;;
  list)   shift; cmd_list   "$@" ;;
  stop)   shift; cmd_stop   "$@" ;;
  cost)   shift; cmd_cost   "$@" ;;
  *) cat >&2 <<'USAGE'
tmuxx.sh start  <name> <workdir> [--worker vibe|claude|<cmd>] [--model sonnet]
                                 [--split | --pane %N]
tmuxx.sh send   <name> [prompt...]        # ohne Argument: Prompt von stdin
tmuxx.sh status <name>                    # idle|busy|dialog|dead (rc 0|3|2|1)
tmuxx.sh await  <name> [timeout-sek]      # blockiert bis idle|dialog|dead (rc wie status, 4=timeout)
tmuxx.sh answer <name> [option]           # blockierende Auswahl beantworten (default 2)
tmuxx.sh peek   <name> [zeilen]
tmuxx.sh key    <name> <taste...>         # z.B. Down Enter
tmuxx.sh list
tmuxx.sh cost   <name>
tmuxx.sh stop   <name>
USAGE
     exit 64 ;;
esac
