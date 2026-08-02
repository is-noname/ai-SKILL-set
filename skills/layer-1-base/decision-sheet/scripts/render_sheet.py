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
import hashlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sheet_spec  # noqa: E402  - liegt daneben, auch im globalen Spiegel
import sheet_state  # noqa: E402

MARKER = "<!--SHEET-DATA-->"
SHARED_DIR = Path.home() / "ai-shared" / "decision-sheet"

# Was setup_global_conventions.sh spiegelt (deploy_decision_sheet). Steht hier, um
# die beiden Ablagen vergleichen zu koennen - faellt spaeter eine Datei dazu, deckt
# der Vergleich sie erst ab, wenn sie auch hier steht.
MIRRORED = (
    "index.html",
    "sheet_spec.py",
    "sheet_state.py",
    "render_sheet.py",
    "fetch_answers.py",
    "resolve_answers.py",
)

REDEPLOY = "bash <ai-SKILL-set>/scripts/setup_global_conventions.sh ~/.claude"


class TemplateMissing(Exception):
    """Weder skill-lokal noch global liegt eine index.html."""


@dataclass(frozen=True)
class Copy:
    """Eine Ablage von Renderer und Scripts - Vorlage plus Fingerabdruck drumherum.

    `files` haelt die sha256 je gespiegelter Datei. Bewusst der Ist-Zustand der
    Dateien und keine mitgeschriebene VERSION-Datei: eine Versionsnotiz sagt nur,
    was beim Deployen galt, der Hash sagt, was jetzt dasteht - und faengt damit auch
    die von Hand angefasste Kopie. Fehlende Dateien fehlen als Schluessel.
    """

    template: Path
    files: dict[str, str] = field(default_factory=dict)


def choose_template(local: Copy | None, shared: Copy | None) -> tuple[Path, str | None]:
    """Welche Vorlage gilt - und was ist dazu zu melden?

    Die Skill-Kopie schlaegt den globalen Spiegel: sie kam mit demselben Pull wie das
    Script, das sie gerade liest, waehrend der Spiegel vom letzten Setup-Lauf auf
    dieser Maschine stammt und beliebig alt sein darf. Umgekehrt ueberstimmte frueher
    ein alter Spiegel jeden frisch gepullten Skill, ohne dass es jemand merkte.

    Reine Auswahl ueber zwei Kandidaten - kein Dateisystem, kein Home-Verzeichnis.
    """
    if local is None and shared is None:
        raise TemplateMissing
    if local is None:
        return shared.template, None  # Hook-Pfad: es gibt nur den Spiegel
    if shared is None:
        return local.template, None

    diff = sorted(n for n in set(local.files) | set(shared.files)
                  if local.files.get(n) != shared.files.get(n))
    if not diff:
        return local.template, None
    return local.template, (
        f"Hinweis: der globale Spiegel weicht vom Skill ab ({', '.join(diff)}) - "
        f"es gilt die Skill-Kopie.\n  Spiegel angleichen: {REDEPLOY}"
    )


def _copy_at(template: Path, files: dict[str, Path]) -> Copy | None:
    """Eine Ablage einlesen - None, wenn dort keine Vorlage liegt."""
    if not template.is_file():
        return None
    hashes = {}
    for name, path in files.items():
        try:
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return Copy(template, hashes)


def local_copy() -> Copy | None:
    """Die Ablage neben diesem Script: assets/index.html plus scripts/*.py.

    Laeuft das Script aus dem Spiegel, gibt es kein assets/ daneben - dann ist hier
    nichts und der Spiegel bleibt uebrig.
    """
    scripts = Path(__file__).resolve().parent
    assets = scripts.parent / "assets"
    files = {n: (assets if n.endswith(".html") else scripts) / n for n in MIRRORED}
    return _copy_at(assets / "index.html", files)


def shared_copy() -> Copy | None:
    """Der globale Spiegel - flach, alles in einem Verzeichnis."""
    return _copy_at(SHARED_DIR / "index.html", {n: SHARED_DIR / n for n in MIRRORED})


def find_template() -> Path:
    """Vorlage waehlen und eine Abweichung der beiden Ablagen melden."""
    try:
        template, note = choose_template(local_copy(), shared_copy())
    except TemplateMissing:
        local = Path(__file__).resolve().parent.parent / "assets" / "index.html"
        raise SystemExit(
            f"Fehler: keine index.html gefunden.\n  gesucht: {local}\n"
            f"           {SHARED_DIR / 'index.html'}\n"
            f"  Renderer global deployen: {REDEPLOY}"
        ) from None
    if note:
        print(note)
    return template


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
