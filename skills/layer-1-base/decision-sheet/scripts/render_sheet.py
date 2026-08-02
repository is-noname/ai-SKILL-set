#!/usr/bin/env python3
"""Baut aus einem Sheet (.jsonl) eine eigenstaendige HTML-Datei und oeffnet sie.

Warum eine Kopie statt eines ?file=-Parameters: unter file:// blockt Chrome
fetch()/XHR auf lokale Dateien. Das Sheet wird deshalb direkt als
<script type="application/json"> in eine Kopie der index.html injiziert - kein
Server, kein Port, kein Prozess der haengen bleibt.

Der Agent ruft immer denselben Befehl auf, egal ob die Hooks eingerichtet sind:
ist der Stop-Hook registriert, wird nur validiert und gebaut (er oeffnet gleich
selbst), sonst geht das Fenster sofort auf. So gibt es genau einen Pfad und kein
Sheet, das unbemerkt liegen bleibt.

Usage:
    python3 render_sheet.py .decisions/ticketsystem-v2.jsonl [--no-open] [--out PFAD]
    python3 render_sheet.py <sheet> --force-open   # Hook-Aufruf: immer oeffnen
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sheet_spec  # noqa: E402  - liegt daneben, auch im globalen Spiegel
import sheet_state  # noqa: E402

MARKER = "<!--SHEET-DATA-->"
SHARED_TEMPLATE = Path.home() / "ai-shared" / "decision-sheet" / "index.html"
HOOK_NAME = "decision-sheet-open"


def stop_hook_active(project: Path) -> bool:
    """Ist der Stop-Hook registriert, der das Sheet von selbst oeffnet?

    Substring-Suche statt JSON-Auswertung: das Hook-Format unterscheidet sich je
    Agent und Version, der Skriptname ist das stabile Merkmal. Ein Treffer in einer
    auskommentierten Zeile gaebe es hier nicht - JSON kennt keine Kommentare.
    """
    candidates = [
        project / ".claude" / "settings.json",
        project / ".claude" / "settings.local.json",
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.local.json",
    ]
    for path in candidates:
        try:
            if HOOK_NAME in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def find_template() -> Path:
    """Global deployte Vorlage bevorzugen, sonst die skill-lokale daneben."""
    local = Path(__file__).resolve().parent.parent / "assets" / "index.html"
    for cand in (SHARED_TEMPLATE, local):
        if cand.is_file():
            return cand
    raise SystemExit(
        f"Fehler: keine index.html gefunden.\n  gesucht: {SHARED_TEMPLATE}\n           {local}\n"
        "  Renderer global deployen: bash scripts/setup_global_conventions.sh ~/.claude"
    )


def validate(sheet_text: str) -> list[str]:
    """Alle Regelverstoesse des Sheets - leere Liste heisst sauber.

    Die Regeln stehen in sheet_spec, nicht hier: derselbe Datensatz wird in die HTML
    injiziert, damit ein per Drag&Drop geladenes Sheet gleich beurteilt wird. Kein
    SystemExit - das uebersetzt der CLI-Wrapper in main(), Aufrufer als Bibliothek
    bekommen die Liste.
    """
    try:
        _head, _questions, errors = sheet_spec.load(sheet_text)
    except sheet_spec.SheetError as exc:
        return [str(exc)]
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Decision Sheet rendern und oeffnen")
    ap.add_argument("sheet", type=Path, help="Pfad zur .jsonl-Datei")
    ap.add_argument("--out", type=Path, help="Zielpfad der HTML (Default: Temp-Verzeichnis)")
    ap.add_argument("--no-open", action="store_true", help="nur bauen, nicht oeffnen")
    ap.add_argument(
        "--force-open",
        action="store_true",
        help="immer oeffnen, Hook-Erkennung ueberspringen (nutzt der Stop-Hook selbst)",
    )
    args = ap.parse_args()

    if not args.sheet.is_file():
        raise SystemExit(f"Fehler: {args.sheet} existiert nicht.")

    sheet_text = args.sheet.read_text(encoding="utf-8")
    errors = validate(sheet_text)
    if errors:
        raise SystemExit("\n".join(f"Fehler: {args.sheet}: {e}" for e in errors))
    head, _questions = sheet_spec.parse_lines(sheet_text)
    slug = head.get("sheet") or args.sheet.stem

    template = find_template().read_text(encoding="utf-8")
    if MARKER not in template:
        raise SystemExit(f"Fehler: {MARKER} fehlt in der Vorlage - falsche oder alte index.html.")

    # </script> im Inhalt wuerde den Block vorzeitig schliessen.
    payload = sheet_text.replace("</", "<\\/")
    block = (
        f'<script id="sheet-data" type="application/json" '
        f'data-name="{slug}">\n{payload}\n</script>'
    )
    out = args.out or Path(tempfile.gettempdir()) / f"sheet-{slug}.html"
    # Spec mitgeben: der Renderer prueft ein spaeter reingezogenes Sheet gegen
    # dieselben Regeln, ohne sie zu kennen.
    out.write_text(sheet_spec.inject(template.replace(MARKER, block)), encoding="utf-8")
    print(f"gerendert: {out}")

    open_it = not args.no_open
    if open_it and not args.force_open:
        if stop_hook_active(sheet_state.project_of(args.sheet)):
            # Der Hook oeffnet und stempelt gleich selbst - hier passiert beides
            # nicht, sonst ueberspringt er das gestempelte Sheet und es ginge nie
            # ein Fenster auf.
            print("Stop-Hook aktiv - das Fenster geht auf, sobald du fertig geantwortet hast.")
            return 0

    if open_it:
        # Wer oeffnet, stempelt: sonst zeigt ein spaeter eingerichteter Hook dasselbe
        # Sheet ein zweites Mal.
        sheet_state.mark_opened(sheet_state.Sheet.at(args.sheet))
        try:
            subprocess.Popen(
                ["xdg-open", str(out)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            print(f"xdg-open nicht gefunden - manuell oeffnen: file://{out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
