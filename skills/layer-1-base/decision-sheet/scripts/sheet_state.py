#!/usr/bin/env python3
"""Der Lebenszyklus eines Sheets: geschrieben -> geoeffnet -> beantwortet -> veraltet.

Dieser Zustand wurde frueher im Stop-Hook aus Rohsignalen rekonstruiert - ein
mtime-Vergleich fuer "beantwortet", ein grep gegen eine Textdatei fuer "geoeffnet",
ein find|sort fuer "das neueste". Drei Fallen, drei Kommentarbloecke, alles in Bash
und damit nur fuer Claude erreichbar. Hier ist der Zustand benannt und pruefbar.

Zwei Fragen beantwortet das Modul:

    pending(project)  -> welches Sheet wartet auf den User (oder keins)?
    mark_opened(sheet) -> dieses Sheet ist gezeigt worden.

Wer oeffnet, stempelt - der Hook wie das Script. Ohne diese Regel wuerde entweder
jeder Turn dasselbe Fenster aufreissen oder gar keins aufgehen.

Der Stempel haelt Pfad + mtime in **Nanosekunden** fest, nicht in Sekunden: eine
Korrektur direkt nach dem Stempeln faellt sonst in dieselbe Sekunde und das
geaenderte Sheet gilt faelschlich als schon gezeigt (Regressionstest in
tests/test_sheet_state.py).

Usage (fuer Hooks und andere Agents; Python-Aufrufer importieren stattdessen):
    python3 sheet_state.py pending <projekt>      # Pfad des wartenden Sheets oder nichts
    python3 sheet_state.py mark-opened <sheet>
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

DECISIONS = ".decisions"
STAMP_NAME = ".opened"


@dataclass(frozen=True)
class Sheet:
    """Ein Sheet mit der mtime, die beim Lesen galt.

    Die mtime gehoert ins Objekt, nicht in einen spaeteren stat()-Aufruf: zwischen
    "welches wartet?" und "gestempelt" liegt das Rendern, und genau dann darf sich
    der Bezugspunkt nicht verschieben.
    """

    path: Path
    mtime_ns: int

    @classmethod
    def at(cls, path: Path) -> Sheet:
        path = Path(path).resolve()
        return cls(path, path.stat().st_mtime_ns)

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def answers(self) -> Path:
        return self.path.with_name(f"{self.slug}.answers.json")

    @property
    def project(self) -> Path:
        return project_of(self.path)

    @property
    def stamp_line(self) -> str:
        return f"{self.path} {self.mtime_ns}"


def decisions_dir(project: Path) -> Path:
    return Path(project) / DECISIONS


def project_of(sheet: Path) -> Path:
    """Projektwurzel = Elternverzeichnis von .decisions/, sonst das Sheet-Verzeichnis."""
    sheet_dir = Path(sheet).resolve().parent
    return sheet_dir.parent if sheet_dir.name == DECISIONS else sheet_dir


def sheets(project: Path) -> list[Sheet]:
    """Alle Sheets des Projekts, neuestes zuerst."""
    found = []
    for path in decisions_dir(project).glob("*.jsonl"):
        try:
            if path.is_file():
                found.append(Sheet.at(path))
        except OSError:
            continue
    return sorted(found, key=lambda s: s.mtime_ns, reverse=True)


def answered(sheet: Sheet) -> bool:
    """Liegt eine Antwort-Datei da, die neuer ist als das Sheet?"""
    try:
        return sheet.answers.stat().st_mtime_ns > sheet.mtime_ns
    except OSError:
        return False


def opened(sheet: Sheet) -> bool:
    """Ist genau dieser Stand des Sheets schon gezeigt worden?

    Ein geaendertes Sheet hat eine andere mtime und gilt damit als ungezeigt - so
    geht ein korrigiertes Sheet wieder auf, ein unveraendertes nicht in jedem Turn.
    """
    return sheet.stamp_line in _stamp_lines(stamp_path(sheet.project))


def pending(project: Path) -> Sheet | None:
    """Das Sheet, das auf den User wartet - oder None.

    Neuestes zuerst, damit pro Turn hoechstens ein Fenster aufgeht und es das
    zuletzt geschriebene ist.
    """
    for sheet in sheets(project):
        if answered(sheet) or opened(sheet):
            continue
        return sheet
    return None


def mark_opened(sheet: Sheet) -> bool:
    """Diesen Stand als gezeigt stempeln. False, wenn .decisions/ nicht schreibbar ist.

    Auch nach einem gescheiterten Rendern stempeln: sonst wiederholt ein defektes
    Sheet seine Fehlermeldung in jedem Turn. Der alte Eintrag desselben Pfads faellt
    weg, damit der Stempel nicht mitwaechst.
    """
    stamp = stamp_path(sheet.project)
    prefix = f"{sheet.path} "
    keep = [ln for ln in _stamp_lines(stamp) if not ln.startswith(prefix)]
    keep.append(sheet.stamp_line)
    tmp = stamp.with_name(stamp.name + ".tmp")
    try:
        tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
        tmp.replace(stamp)
    except OSError:
        return False
    return True


def stamp_path(project: Path) -> Path:
    return decisions_dir(project) / STAMP_NAME


def _stamp_lines(stamp: Path) -> list[str]:
    try:
        return [ln for ln in stamp.read_text(encoding="utf-8").splitlines() if ln]
    except OSError:
        return []


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: sheet_state.py pending <projekt> | mark-opened <sheet>", file=sys.stderr)
        return 2
    cmd, arg = argv

    if cmd == "pending":
        sheet = pending(Path(arg))
        if sheet is None:
            return 1
        print(sheet.path)
        return 0

    if cmd == "mark-opened":
        path = Path(arg)
        if not path.is_file():
            return 1
        return 0 if mark_opened(Sheet.at(path)) else 1

    print(f"unbekanntes Kommando: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
