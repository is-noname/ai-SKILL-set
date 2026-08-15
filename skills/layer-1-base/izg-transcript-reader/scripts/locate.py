#!/usr/bin/env python3
"""Lade-Mechanik fuer konsumierende Skills (IZG-T-146).

Wer dieses Modul importiert hat den Reader bereits gefunden - der Bootstrap
(zwei Kandidatenpfade auf sys.path) bleibt zwangslaeufig beim Aufrufer, weil
er noch vor jedem Import aus diesem Skill laufen muss. Alles danach steht
hier: das Laden unter einem eindeutigen Modulnamen und das Re-Exportieren.

Warum ueberhaupt eine eigene Lade-Funktion statt `import transcript`:
`izg-benchmark-actions/scripts/transcript.py` heisst selbst so. Ein normaler
Import wuerde dort in sys.modules auf die noch unfertige eigene Datei
zurueckverweisen statt das Modul dieses Skills zu laden. Der Praefix unten
haelt beide Module auseinander - unabhaengig davon, wie der Aufrufer heisst.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PREFIX = "_izg_transcript_reader"

SCRIPTS_DIR = Path(__file__).resolve().parent


def load(name: str = "transcript") -> ModuleType:
    """Laedt ein Modul dieses Skills unter eindeutigem sys.modules-Namen.

    Args:
        name: Modulname ohne `.py`, per Default der Transcript-Adapter.

    Returns:
        Das geladene Modul. Wiederholte Aufrufe liefern dieselbe Instanz.
    """
    key = f"{MODULE_PREFIX}.{name}"
    cached = sys.modules.get(key)
    if cached is not None:
        return cached

    path = SCRIPTS_DIR / f"{name}.py"
    if not path.is_file():
        raise ImportError(f"izg-transcript-reader hat kein Modul '{name}' ({path}).")

    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[key]
        raise
    return module


def re_export(namespace: dict, names: list[str], module: ModuleType | None = None) -> ModuleType:
    """Kopiert die genannten Namen aus dem Reader in ein Aufrufer-Namespace.

    Args:
        namespace: Ziel, ueblicherweise `globals()` des aufrufenden Moduls.
        names: Zu uebernehmende oeffentliche Namen.
        module: Quellmodul, per Default der Transcript-Adapter.

    Returns:
        Das Quellmodul, damit der Aufrufer weitere Namen direkt greifen kann.
    """
    source = module if module is not None else load()
    for n in names:
        try:
            namespace[n] = getattr(source, n)
        except AttributeError as exc:
            raise ImportError(
                f"izg-transcript-reader kennt '{n}' nicht - Interface hat sich "
                f"geaendert (verfuegbar u.a.: {', '.join(sorted(vars(source))[:8])})."
            ) from exc
    return source
