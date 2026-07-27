#!/usr/bin/env python3
"""Erzeugt ein Desktop-Startericon plus Launcher-Wrapper fuer eine Server-App.

Der erzeugte Launcher beendet beim Klick eventuell laufende Instanzen der App,
startet den Server losgeloest (kein dauerhaftes Terminal) und oeffnet optional
den Browser. Ein eventuell oeffnendes Terminalfenster wird automatisch
geschlossen.

Beispiel:
    make_starter_icon.py \
        --name "Stonky" \
        --workdir "$HOME/Dokumente/AI/Stonky" \
        --start "python3 app.py" \
        --port 8501 \
        --url "http://localhost:8501" \
        --match "app.py"

Erzeugt:
    ~/.local/bin/stonky-launcher.sh        (Wrapper-Skript)
    ~/Schreibtisch/Stonky.desktop          (Startericon, ausfuehrbar + trusted)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "app"


def desktop_dir() -> Path:
    """Ermittelt den Desktop-Ordner (XDG, faellt auf ~/Desktop bzw. ~/Schreibtisch zurueck)."""
    try:
        out = subprocess.run(
            ["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=False
        ).stdout.strip()
        if out and Path(out).is_dir():
            return Path(out)
    except FileNotFoundError:
        pass
    for cand in (Path.home() / "Schreibtisch", Path.home() / "Desktop"):
        if cand.is_dir():
            return cand
    return Path.home() / "Desktop"


LAUNCHER_TEMPLATE = r"""#!/usr/bin/env bash
# Auto-generiert von izg-starter-icon-mkr. Startet {NAME}.
# Beendet laufende Instanzen, startet den Server losgeloest und oeffnet die App.
set -u

APP_NAME={NAME_Q}
WORKDIR={WORKDIR_Q}
START_CMD={START_Q}
PORT={PORT}
URL={URL_Q}
MATCH={MATCH_Q}
LOG_DIR="$HOME/.local/share/izg-starter/logs"
LOG_FILE="$LOG_DIR/{SLUG}.log"

mkdir -p "$LOG_DIR"

notify() {{
    command -v notify-send >/dev/null 2>&1 && notify-send "$APP_NAME" "$1" || true
}}

# --- 1. Laufende Instanzen beenden -------------------------------------------
stop_running() {{
    if [ -n "$PORT" ]; then
        # Prozesse, die den Port belegen, sauber beenden
        local pids
        pids="$(fuser -n tcp "$PORT" 2>/dev/null | tr -s ' ')"
        if [ -n "$pids" ]; then
            kill $pids 2>/dev/null || true
            sleep 1
            fuser -k -n tcp "$PORT" 2>/dev/null || true
        fi
    fi
    if [ -n "$MATCH" ]; then
        # eigene PID und die des pkill ausschliessen
        pkill -f -- "$MATCH" 2>/dev/null || true
        sleep 1
        pkill -9 -f -- "$MATCH" 2>/dev/null || true
    fi
}}

# --- 2. Server losgeloest starten --------------------------------------------
start_app() {{
    cd "$WORKDIR" || {{ notify "Arbeitsverzeichnis fehlt: $WORKDIR"; exit 1; }}
    # setsid + nohup => Server haengt nicht am Terminal und ueberlebt dessen Schliessen
    setsid bash -c "exec $START_CMD" >>"$LOG_FILE" 2>&1 < /dev/null &
    disown 2>/dev/null || true
}}

# --- 3. Auf Port warten (falls gesetzt) --------------------------------------
wait_for_port() {{
    [ -z "$PORT" ] && {{ sleep 2; return 0; }}
    for _ in $(seq 1 40); do
        if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
            exec 3>&- 3<&-
            return 0
        fi
        sleep 0.5
    done
    return 1
}}

# --- 4. Browser/URL oeffnen --------------------------------------------------
open_url() {{
    [ -z "$URL" ] && return 0
    xdg-open "$URL" >/dev/null 2>&1 || true
}}

# --- 5. Eventuelles Terminalfenster automatisch schliessen --------------------
close_own_terminal() {{
    # Nur wenn ueber ein Terminal gestartet (Terminal=true Fallback).
    command -v xdotool >/dev/null 2>&1 || return 0
    local win
    win="$(xdotool getactivewindow 2>/dev/null)" || return 0
    local wname
    wname="$(xdotool getwindowname "$win" 2>/dev/null || true)"
    case "$wname" in
        *erminal*|*onsole*|*xterm*|*Tilix*|*Kitty*|*Alacritty*)
            xdotool windowkill "$win" 2>/dev/null || true
            ;;
    esac
}}

stop_running
start_app
if wait_for_port; then
    open_url
else
    notify "Server-Port $PORT nicht erreichbar - Log: $LOG_FILE"
fi
close_own_terminal
exit 0
"""

DESKTOP_TEMPLATE = """[Desktop Entry]
Version=1.0
Type=Application
Name={NAME}
Comment=Startet {NAME} (beendet alte Instanzen, startet Server)
Exec={LAUNCHER}
Icon={ICON}
Terminal={TERMINAL}
Categories=Utility;
StartupNotify=true
"""


def sh_quote(value: str) -> str:
    """Single-quote fuer sichere Einbettung in das Bash-Template."""
    return "'" + value.replace("'", "'\\''") + "'"


def main() -> int:
    p = argparse.ArgumentParser(description="Desktop-Startericon fuer eine Server-App erzeugen.")
    p.add_argument("--name", required=True, help="Anzeigename der App (z.B. 'Stonky')")
    p.add_argument("--workdir", required=True, help="Arbeitsverzeichnis der App")
    p.add_argument("--start", required=True, help="Startbefehl (z.B. 'python3 app.py')")
    p.add_argument("--port", default="", help="TCP-Port des Servers (fuer Kill + Warten)")
    p.add_argument("--url", default="", help="URL zum Oeffnen (default: http://localhost:PORT)")
    p.add_argument("--match", default="",
                   help="Prozess-Pattern fuer pkill -f (default: Startbefehl)")
    p.add_argument("--icon", default="auto",
                   help="'auto' (Custom-SVG generieren, Default), Theme-Icon-Name "
                        "oder absoluter Pfad zu einem Bild")
    p.add_argument("--glyph", choices=["letter", "play", "terminal", "rhombus"],
                   default="letter",
                   help="Glyph der generierten Kachel bei --icon auto (Default: letter)")
    p.add_argument("--show-terminal", action="store_true",
                   help="Terminal sichtbar lassen (wird nach Start automatisch geschlossen)")
    p.add_argument("--bindir", default=str(Path.home() / ".local" / "bin"),
                   help="Zielordner fuer das Launcher-Skript")
    args = p.parse_args()

    slug = slugify(args.name)
    workdir = str(Path(args.workdir).expanduser())
    if not Path(workdir).is_dir():
        print(f"WARNUNG: Arbeitsverzeichnis existiert nicht: {workdir}", file=sys.stderr)

    url = args.url or (f"http://localhost:{args.port}" if args.port else "")
    match = args.match or args.start

    # --- Icon bestimmen: 'auto' => Custom-SVG generieren ---
    icon = args.icon
    if icon == "auto":
        icon_dir = Path.home() / ".local" / "share" / "icons"
        icon_dir.mkdir(parents=True, exist_ok=True)
        icon = str(icon_dir / f"{slug}.svg")
        make_icon = Path(__file__).with_name("make_icon.py")
        subprocess.run(
            [sys.executable, str(make_icon), "--name", args.name,
             "--glyph", args.glyph, "--out", icon],
            check=False,
        )
    elif "/" in icon:
        icon = str(Path(icon).expanduser())

    # --- Launcher-Skript schreiben ---
    bindir = Path(args.bindir).expanduser()
    bindir.mkdir(parents=True, exist_ok=True)
    launcher_path = bindir / f"{slug}-launcher.sh"
    launcher = LAUNCHER_TEMPLATE.format(
        NAME=args.name,
        NAME_Q=sh_quote(args.name),
        SLUG=slug,
        WORKDIR_Q=sh_quote(workdir),
        START_Q=sh_quote(args.start),
        PORT=args.port,
        URL_Q=sh_quote(url),
        MATCH_Q=sh_quote(match),
    )
    launcher_path.write_text(launcher, encoding="utf-8")
    launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # --- .desktop schreiben ---
    desk_dir = desktop_dir()
    desk_dir.mkdir(parents=True, exist_ok=True)
    desktop_path = desk_dir / f"{args.name}.desktop"
    desktop = DESKTOP_TEMPLATE.format(
        NAME=args.name,
        LAUNCHER=str(launcher_path),
        ICON=icon,
        TERMINAL="true" if args.show_terminal else "false",
    )
    desktop_path.write_text(desktop, encoding="utf-8")
    desktop_path.chmod(desktop_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # --- Als vertrauenswuerdig markieren (Cinnamon/Nemo/GNOME) ---
    if shutil.which("gio"):
        subprocess.run(["gio", "set", str(desktop_path), "metadata::trusted", "true"],
                       check=False)
    # Auch im Anwendungsmenue verfuegbar machen
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    try:
        (apps_dir / f"{slug}.desktop").write_text(desktop, encoding="utf-8")
    except OSError:
        pass

    print("OK - Startericon erstellt:")
    print(f"  Launcher : {launcher_path}")
    print(f"  Desktop  : {desktop_path}")
    print(f"  Menue    : {apps_dir / (slug + '.desktop')}")
    print(f"  Log      : ~/.local/share/izg-starter/logs/{slug}.log")
    if url:
        print(f"  URL      : {url}")
    print("\nHinweis: In Cinnamon ggf. einmal Rechtsklick -> 'Starten erlauben' "
          "falls das Icon noch als Textdatei erscheint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
