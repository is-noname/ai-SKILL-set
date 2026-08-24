#!/usr/bin/env bash
# Interaktiver Ticket-Picker fuer ein tmux-Popup: waehlt ein offenes Ticket per
# fzf und schickt einen Arbeitsauftrag an TARGET_PANE (pane_id, per Env gesetzt,
# vom Aufrufer VOR dem Oeffnen des Popups eingefangen).
# Usage: TARGET_PANE=%3 bash scripts/ticket_picker.sh <projekt-pfad>
# Faellt auf FALLBACK_PROJECT zurueck, wenn unter <projekt-pfad> kein
# tickets/open existiert (z.B. Pane liegt gerade nicht in einem Projekt
# mit Ticketsystem).
set -u
FALLBACK_PROJECT="/home/izg/Dokumente/AI/00_chuck/CFO"
TARGET="${1:-.}"
OPEN_DIR="$TARGET/tickets/open"

[ -n "${TARGET_PANE:-}" ] || { echo "TARGET_PANE nicht gesetzt"; read -r -p "Enter zum Schliessen"; exit 1; }
command -v fzf >/dev/null || { echo "fzf fehlt (sudo apt install fzf)"; read -r -p "Enter zum Schliessen"; exit 1; }

if [ ! -d "$OPEN_DIR" ] && [ -d "$FALLBACK_PROJECT/tickets/open" ]; then
  TARGET="$FALLBACK_PROJECT"
  OPEN_DIR="$TARGET/tickets/open"
fi

[ -d "$OPEN_DIR" ] || { echo "Kein tickets/open unter $TARGET"; read -r -p "Enter zum Schliessen"; exit 1; }

# Typ-Badge einfaerben (24-bit ANSI aus /home/izg/.claude/design-tokens.md,
# wird von fzf --ansi gerendert)
badge_for_type() {
  local t="$1" rgb
  case "$t" in
    feature) rgb="96;165;250" ;;  # --blue
    bug)     rgb="248;113;113" ;; # --red
    chore)   rgb="251;191;36" ;;  # --yellow
    docs)    rgb="6;252;153" ;;   # Akzent (Canto Green)
    *)       rgb="136;136;136" ;; # --muted
  esac
  printf '\033[1;38;2;%sm[%s]\033[0m' "$rgb" "${t:-?}"
}

# Priority-Icon
icon_for_prio() {
  case "$1" in
    high|hoch|urgent|dringend) printf '🔥' ;;
    low|niedrig)               printf '🐢' ;;
    *)                         printf '⚪' ;;
  esac
}

# Syntax-Highlighting im Preview, wenn bat verfuegbar ist, sonst cat
BAT_BIN=""
command -v bat >/dev/null && BAT_BIN="bat"
[ -z "$BAT_BIN" ] && command -v batcat >/dev/null && BAT_BIN="batcat"
if [ -n "$BAT_BIN" ]; then
  PREVIEW_CMD="$BAT_BIN --style=numbers,changes --color=always --theme=Nord --language=markdown -- {4}"
else
  PREVIEW_CMD="cat -- {4}"
fi

LINES=""
COUNT=0
for f in "$OPEN_DIR"/*.md; do
  [ -f "$f" ] || continue
  id="$(grep -m1 '^id:' "$f" | cut -d' ' -f2-)"
  [ -z "$id" ] && continue
  title="$(grep -m1 '^title:' "$f" | cut -d' ' -f2-)"
  type="$(grep -m1 '^type:' "$f" | cut -d' ' -f2-)"
  prio="$(grep -m1 '^priority:' "$f" | cut -d' ' -f2-)"
  badge="$(badge_for_type "$type")"
  picon="$(icon_for_prio "$prio")"
  LINES+="${id}"$'\t'"${title}"$'\t'"${badge} ${picon} ${prio}"$'\t'"${f}"$'\n'
  COUNT=$((COUNT + 1))
done

if [ -z "$LINES" ]; then
  echo "Keine offenen Tickets in $OPEN_DIR."
  read -r -p "Enter zum Schliessen"
  exit 0
fi

# Design-Token-Palette, angeglichen an kitty-Hintergrund #262624 (siehe
# skills/layer-1-base/izg-tmuxxing/configs/kitty.conf)
DESIGN_TOKENS="fg:#e5e4df,bg:-1,hl:#06fc99,fg+:#e5e4df,bg+:#302f2c,hl+:#06fc99,info:#888888,prompt:#06fc99,pointer:#06fc99,marker:#06fc99,spinner:#06fc99,header:#888888,border:#3a3a38"

SELECTED="$(printf '%s' "$LINES" | fzf \
  --ansi \
  --delimiter=$'\t' \
  --with-nth=1,2,3 \
  --prompt="🎫 Ticket > " \
  --pointer="▶" \
  --marker="✓" \
  --header="$(printf '%d offene Tickets in %s' "$COUNT" "$TARGET")" \
  --header-first \
  --layout=reverse \
  --border=rounded \
  --info=inline \
  --color="$DESIGN_TOKENS" \
  --preview="$PREVIEW_CMD" \
  --preview-window='right:55%:wrap:border-left')"
[ -z "$SELECTED" ] && exit 0

ID="$(printf '%s' "$SELECTED" | cut -f1)"
TITLE="$(printf '%s' "$SELECTED" | cut -f2)"

tmux send-keys -t "$TARGET_PANE" -l "arbeite an ${ID}: ${TITLE}"
tmux send-keys -t "$TARGET_PANE" Enter
