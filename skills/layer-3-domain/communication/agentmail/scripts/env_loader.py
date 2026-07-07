"""Laedt die Skill-eigene .env direkt in os.environ (stdlib-only).

Ersetzt das bisherige, implizite "Shell sourcen"-Vorgehen. Das brach bei jedem
Wert mit Leerzeichen (z.B. `OWNER_NAME=Alexander Czapla,...`): `bash source .env`
interpretiert den Teil nach dem ersten Leerzeichen als eigenes Kommando statt
als Teil des Werts, die Variable kam leer oder abgeschnitten im Prozess an
(Namens-Redaction griff dadurch nicht, siehe Cannaseur-Testlauf 2026-07-07).

Kein python-dotenv als neue Dependency - schlanker Minimal-Parser, gleicher
Stil wie an anderen Stellen im Repo ueblich.
"""

from __future__ import annotations

import os
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_env(path: Path = _ENV_FILE) -> None:
    """Parst KEY=VALUE-Zeilen aus `path` und setzt sie in os.environ.

    Bereits gesetzte Umgebungsvariablen werden nicht ueberschrieben. Leere
    Zeilen und `#`-Kommentare werden uebersprungen. Werte duerfen optional in
    einfache oder doppelte Anfuehrungszeichen gefasst sein - noetig fuer Werte
    mit Leerzeichen/Kommas wie `OWNER_NAME`.
    """
    if not path.is_file():
        return
    for zeile in path.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        key, _, value = zeile.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = _strip_quotes(value.strip())


load_env()
