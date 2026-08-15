#!/usr/bin/env python3
"""Duenner Shim auf das Formatwissen aus dem Skill `izg-transcript-reader`.

Das eigentliche Transcript-Format (Slug, Parsing, Entdopplung, Paarung,
content-Gestalten) ist dorthin ausgelagert (IZG-T-139) - hier bleibt nur die
Weiterreichung, damit `import transcript` in diesem Skillordner unveraendert
funktioniert (bench.py, tests/test_transcript.py).

Lade-Mechanik und Re-Export liegen in `locate.py` des Readers (IZG-T-146);
hier steht nur noch der Bootstrap, der ihn ueberhaupt erst auffindbar macht.

Interface: unveraendert - transcript_path() zum Auffinden, read_session()
zum Einlesen.
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Bootstrap izg-transcript-reader (bewusst identisch in jedem konsumierenden
# Skill): muss vor jedem Import aus dem Reader laufen und kann daher nicht
# selbst dorthin wandern. Nach dem Pull liegen Skills flach nebeneinander
# (.claude/skills/<name>/), im Repo verschachtelt nach Layer - ein fester
# relativer Import haelt nur in einer der beiden Welten.
_READER = "izg-transcript-reader"
_skill_root = Path(__file__).resolve().parent.parent
_candidates = [
    _skill_root.parent / _READER / "scripts",  # Zielprojekt (flach)
    _skill_root.parent.parent.parent / "layer-1-base" / _READER / "scripts",  # Repo
]
for _c in _candidates:
    if (_c / "locate.py").is_file():
        sys.path.insert(0, str(_c))
        break
else:
    raise ImportError(
        f"{_READER} nicht gefunden. Erwartet unter {_candidates[0]} (Zielprojekt) "
        f"oder {_candidates[1]} (Repo). Skill fehlt in den dependencies oder "
        "wurde nicht mitgepullt."
    )

import locate as _locate  # noqa: E402
# --- Ende Bootstrap

# Re-Export des genutzten Interfaces - Aufrufer und Tests greifen weiterhin
# ueber dieses Modul zu.
_shared = _locate.re_export(globals(), [
    "SessionUsage",
    "CHARS_PER_TOKEN",
    "project_slug",
    "transcript_path",
    "find_transcripts",
    "read_session",
])
