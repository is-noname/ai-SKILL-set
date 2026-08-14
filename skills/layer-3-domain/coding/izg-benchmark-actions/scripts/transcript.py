#!/usr/bin/env python3
"""Duenner Shim auf das Formatwissen aus dem Skill `izg-transcript-reader`.

Das eigentliche Transcript-Format (Slug, Parsing, Entdopplung, Paarung,
content-Gestalten) ist dorthin ausgelagert (IZG-T-139) - hier bleibt nur die
Weiterreichung, damit `import transcript` in diesem Skillordner unveraendert
funktioniert (bench.py, tests/test_transcript.py).

Ueber `importlib` statt `import transcript`: diese Datei heisst selbst
`transcript.py`, ein normaler `import transcript` innerhalb dieser Datei
wuerde in sys.modules auf sich selbst zurueckverweisen (noch unfertig
initialisiert) statt das gleichnamige Modul aus izg-transcript-reader zu
laden.

Interface: unveraendert - transcript_path() zum Auffinden, read_session()
zum Einlesen.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_shared_transcript():
    """Loest den Skillgrenzen-uebergreifenden Import zur Laufzeit auf.

    Nach `pull_skill.py` liegen Skills flach nebeneinander
    (.claude/skills/<name>/), im Repo dagegen verschachtelt nach Layer. Ein
    fester relativer Import haelt daher nur in einer der beiden Welten.
    """
    skill_root = Path(__file__).resolve().parent.parent
    candidates = [
        skill_root.parent / "izg-transcript-reader" / "scripts" / "transcript.py",  # Zielprojekt (flach)
        skill_root.parent.parent.parent / "layer-1-base" / "izg-transcript-reader"
        / "scripts" / "transcript.py",  # Repo
    ]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("_izg_transcript_reader", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        "izg-transcript-reader nicht gefunden. Erwartet unter "
        f"{candidates[0]} (Zielprojekt) oder {candidates[1]} (Repo). "
        "Skill fehlt in den dependencies oder wurde nicht mitgepullt."
    )


_shared = _load_shared_transcript()

# Re-Export des kompletten oeffentlichen Interfaces - Aufrufer und Tests
# greifen weiterhin ueber dieses Modul zu.
SessionUsage = _shared.SessionUsage
CHARS_PER_TOKEN = _shared.CHARS_PER_TOKEN
project_slug = _shared.project_slug
transcript_path = _shared.transcript_path
find_transcripts = _shared.find_transcripts
read_session = _shared.read_session
