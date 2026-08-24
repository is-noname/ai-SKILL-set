#!/usr/bin/env bash
# Interaktiver Datei-Picker fuer ein tmux-Popup: durchsucht den Projektbaum per
# fzf (mit bat-Preview rechts), oeffnet die Auswahl fullscreen in nano zum
# Bearbeiten und springt danach zurueck in die Liste (Loop bis Esc/Abbruch).
# Usage: bash scripts/file_picker.sh <projekt-pfad>
set -u
TARGET="${1:-.}"

command -v fzf >/dev/null || { echo "fzf fehlt (sudo apt install fzf)"; read -r -p "Enter zum Schliessen"; exit 1; }
[ -d "$TARGET" ] || { echo "Verzeichnis nicht gefunden: $TARGET"; read -r -p "Enter zum Schliessen"; exit 1; }

BAT_BIN=""
command -v bat >/dev/null && BAT_BIN="bat"
[ -z "$BAT_BIN" ] && command -v batcat >/dev/null && BAT_BIN="batcat"
if [ -n "$BAT_BIN" ]; then
  PREVIEW_CMD="$BAT_BIN --style=numbers,changes --color=always -- {}"
else
  PREVIEW_CMD="cat -- {}"
fi

# Design-Token-Palette, angeglichen an kitty-Hintergrund #262624 (siehe
# skills/layer-1-base/izg-tmuxxing/configs/kitty.conf)
DESIGN_TOKENS="fg:#e5e4df,bg:-1,hl:#06fc99,fg+:#e5e4df,bg+:#302f2c,hl+:#06fc99,info:#888888,prompt:#06fc99,pointer:#06fc99,marker:#06fc99,spinner:#06fc99,header:#888888,border:#3a3a38"

EXCLUDES=(-path '*/.git' -o -path '*/node_modules' -o -path '*/__pycache__' -o -path '*/.idea' -o -path '*/.vscode' -o -path '*/.gemini')

while true; do
  SELECTED="$(cd "$TARGET" && find . \( "${EXCLUDES[@]}" \) -prune -o -type f -print \
      | sed 's#^\./##' \
      | fzf \
          --prompt="📝 Datei > " \
          --pointer="▶" \
          --marker="✓" \
          --header="$(printf 'Editieren in %s (Enter=nano, Esc=schliessen)' "$TARGET")" \
          --header-first \
          --layout=reverse \
          --border=rounded \
          --info=inline \
          --color="$DESIGN_TOKENS" \
          --preview="$PREVIEW_CMD" \
          --preview-window='right:55%:wrap:border-left')"
  [ -z "$SELECTED" ] && exit 0
  nano -- "$TARGET/$SELECTED"
done
