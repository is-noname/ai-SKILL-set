#!/usr/bin/env python3
"""Baut aus einem Sheet (.jsonl) eine eigenstaendige HTML-Datei und oeffnet sie.

Warum eine Kopie statt eines ?file=-Parameters: unter file:// blockt Chrome
fetch()/XHR auf lokale Dateien. Das Sheet wird deshalb direkt als
<script type="application/json"> in eine Kopie der index.html injiziert - kein
Server, kein Port, kein Prozess der haengen bleibt.

Wer hier landet, bekommt ein Fenster - ohne Ausnahme und ohne zu fragen, ob
irgendwo ein Hook registriert ist. Das Oeffnen stempelt das Sheet (sheet_state),
und der Stop-Hook nimmt sich nur ungestempelte Sheets vor. Er ist damit reiner
Nachzuegler fuer Sheets, die an diesem Script vorbei entstanden sind, und kann
sich nicht mit ihm ins Gehege kommen.

Usage:
    python3 render_sheet.py .decisions/ticketsystem-v2.jsonl [--no-open] [--out PFAD]
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

    if not args.no_open:
        # Wer oeffnet, stempelt: sonst zeigt der Stop-Hook dasselbe Sheet gleich
        # noch einmal - der Stempel ist genau das Signal, an dem er vorbeigeht.
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
