#!/usr/bin/env python3
"""Baut aus einem Sheet (.jsonl) eine eigenstaendige HTML-Datei und oeffnet sie.

Warum eine Kopie statt eines ?file=-Parameters: unter file:// blockt Chrome
fetch()/XHR auf lokale Dateien. Das Sheet wird deshalb direkt als
<script type="application/json"> in eine Kopie der index.html injiziert - kein
Server, kein Port, kein Prozess der haengen bleibt.

Usage:
    python3 render_sheet.py .decisions/ticketsystem-v2.jsonl [--no-open] [--out PFAD]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

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


def validate(sheet_text: str, path: Path) -> dict:
    """Prueft das Sheet zeilenweise und gibt den Header zurueck."""
    objs = []
    for lineno, raw in enumerate(sheet_text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            objs.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Fehler: {path}:{lineno} ist kein gueltiges JSON - {exc}")
    if not objs:
        raise SystemExit(f"Fehler: {path} ist leer.")

    head = objs.pop(0) if "id" not in objs[0] else {}
    if not objs:
        raise SystemExit(f"Fehler: {path} enthaelt nur einen Header, keine Fragen.")

    valid_types = {"pick", "multi", "yn", "text"}
    seen: set[str] = set()
    for q in objs:
        qid = str(q.get("id", ""))
        if not qid:
            raise SystemExit(f"Fehler: Frage ohne 'id' in {path}: {q}")
        if qid in seen:
            raise SystemExit(f"Fehler: doppelte id '{qid}' in {path}")
        seen.add(qid)
        if not q.get("q"):
            raise SystemExit(f"Fehler: Frage #{qid} hat kein 'q' (Fragetext).")
        qtype = q.get("t", "pick")
        if qtype not in valid_types:
            raise SystemExit(
                f"Fehler: Frage #{qid} hat t='{qtype}' - erlaubt: {', '.join(sorted(valid_types))}"
            )
        if qtype in ("pick", "multi") and not q.get("o"):
            raise SystemExit(f"Fehler: Frage #{qid} ist '{qtype}', hat aber keine Optionen ('o').")
    for q in objs:
        if "dep" in q and str(q["dep"][0]) not in seen:
            raise SystemExit(f"Fehler: Frage #{q['id']} haengt an unbekannter id '{q['dep'][0]}'.")
    return head


def main() -> int:
    ap = argparse.ArgumentParser(description="Decision Sheet rendern und oeffnen")
    ap.add_argument("sheet", type=Path, help="Pfad zur .jsonl-Datei")
    ap.add_argument("--out", type=Path, help="Zielpfad der HTML (Default: Temp-Verzeichnis)")
    ap.add_argument("--no-open", action="store_true", help="nur bauen, nicht oeffnen")
    args = ap.parse_args()

    if not args.sheet.is_file():
        raise SystemExit(f"Fehler: {args.sheet} existiert nicht.")

    sheet_text = args.sheet.read_text(encoding="utf-8")
    head = validate(sheet_text, args.sheet)
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
    out.write_text(template.replace(MARKER, block), encoding="utf-8")
    print(f"gerendert: {out}")

    if not args.no_open:
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
