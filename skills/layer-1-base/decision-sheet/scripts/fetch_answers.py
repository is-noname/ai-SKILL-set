#!/usr/bin/env python3
"""Holt eine exportierte Decision-Sheet-Antwortdatei ab und gibt sie aus.

Sucht die neueste passende *.answers.json im Download-Ordner, verschiebt sie nach
<projekt>/.decisions/ und schreibt den Inhalt auf stdout.

Zwei Aufrufer teilen sich diese Logik:
  - decision-answers.sh (UserPromptSubmit-Hook) bei "#answers" - stdout landet
    automatisch im Kontext des Agenten.
  - der Agent selbst per Bash, wenn der Hook auf dem System nicht eingerichtet ist.

Usage:
    python3 fetch_answers.py [--project DIR] [--slug SLUG]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Nachbarmodul - liegt sowohl im Skill als auch im globalen Spiegel daneben.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolve_answers  # noqa: E402

CHROME_SUFFIX = re.compile(r" \(\d+\)(\.answers\.json)$")


def download_dirs() -> list[Path]:
    """XDG-Downloadordner plus englische und deutsche Variante, dedupliziert."""
    cands: list[Path] = []
    try:
        xdg = subprocess.run(
            ["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if xdg:
            cands.append(Path(xdg))
    except (OSError, subprocess.SubprocessError):
        pass
    cands += [Path.home() / "Downloads", Path.home() / "Download"]

    out: list[Path] = []
    for c in cands:
        if not c.is_dir():
            continue
        # xdg-user-dir liefert meist dasselbe Verzeichnis wie ~/Downloads - sonst
        # taucht jeder Treffer doppelt auf.
        if any(os.path.samefile(c, seen) for seen in out):
            continue
        out.append(c)
    return out


def newest(dirs: list[Path], pattern: str) -> Path | None:
    hits = [p for d in dirs for p in d.glob(pattern) if p.is_file()]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Decision-Sheet-Antworten abholen")
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="Projektwurzel (Default: cwd)")
    ap.add_argument("--slug", default="", help="Sheet-Slug; ohne Angabe die neueste Datei")
    args = ap.parse_args()

    slug = args.slug.strip().removesuffix(".answers.json")
    pattern = f"{slug or '*'}.answers.json"
    target_dir = args.project / ".decisions"

    dl = download_dirs()
    found = newest(dl, pattern)

    if found is not None:
        target_dir.mkdir(parents=True, exist_ok=True)
        # Chrome haengt bei Namenskollision " (1)" an - auf den Basisnamen zurueckfuehren.
        dest = target_dir / CHROME_SUFFIX.sub(r"\1", found.name)
        try:
            shutil.move(str(found), str(dest))
            answers = dest
        except OSError as exc:
            print(f"Hinweis: Verschieben nach {dest} fehlgeschlagen ({exc}), lese aus {found}.")
            answers = found
    else:
        # Nichts Neues im Download-Ordner - vielleicht schon manuell abgelegt.
        answers = newest([target_dir], pattern) if target_dir.is_dir() else None

    if answers is None:
        searched = ", ".join(str(d) for d in dl) or "<kein Download-Ordner>"
        print(f"Keine Antwort-Datei gefunden (gesucht: {pattern} in {searched} und {target_dir}).")
        print("Im Renderer auf 'Export' -> 'Datei speichern' klicken, dann erneut abholen.")
        return 0

    sheet = answers.with_name(answers.name.removesuffix(".answers.json") + ".jsonl")
    print(f"Decision-Sheet-Antworten aus: {answers}")

    # Die Rohdatei ist ohne das Sheet bedeutungslos (uebernommene Empfehlungen
    # fehlen darin). Liegt das Sheet daneben, geht die aufgeloeste Tabelle raus.
    if sheet.is_file():
        print(f"Zugehoeriges Sheet: {sheet}\n")
        try:
            print(resolve_answers.format_report(resolve_answers.resolve_all(sheet, answers)))
            return 0
        except (OSError, ValueError) as exc:
            print(f"Aufloesung fehlgeschlagen ({exc}) - Rohdatei folgt.")

    print("Kein Sheet daneben - Rohdatei (Interpretation: SKILL.md, Modus 2):")
    print(answers.read_text(encoding="utf-8").strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
