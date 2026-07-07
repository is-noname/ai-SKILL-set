"""Ordnet eingehende AgentMail-Threads per Label einem Projekt-Prefix zu.

Nutzt dieselbe Registry wie die globale doc-ids/tickets-Konvention
(`project-identifier.md`), damit Label-Slug und Projekt-Prefix nicht doppelt
gepflegt werden müssen.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_REGISTRY = Path(os.path.expanduser("~/ai-shared/project-identifier.md"))

_ROW_RE = re.compile(r"^\|\s*`?([A-Za-z0-9]+)`?\s*\|\s*([^|]+?)\s*\|\s*$")


def load_known_slugs(registry_path: Path = DEFAULT_REGISTRY) -> dict[str, str]:
    """Liest die Prefix-Registry und gibt {lowercase-slug: projektname} zurück.

    Gibt ein leeres dict zurück, wenn die Registry-Datei fehlt, statt
    abzubrechen - Routing degradiert dann auf "unassigned" statt zu crashen.
    """
    if not registry_path.exists():
        return {}
    slugs: dict[str, str] = {}
    for line in registry_path.read_text().splitlines():
        match = _ROW_RE.match(line.strip())
        if not match:
            continue
        prefix, project = match.groups()
        if prefix.lower() == "prefix":
            continue
        slugs[prefix.lower()] = project
    return slugs


def route_by_labels(labels: list[str], known_slugs: dict[str, str]) -> str | None:
    """Gibt den ersten Label-Slug zurück, der einem bekannten Projekt-Prefix entspricht.

    Gibt None zurück, wenn kein Label matcht - z.B. bei einer neuen (nicht
    Reply-)Mail ohne vorheriges Projekt-Label. Das ist eine bekannte Grenze
    dieser Routing-Strategie, siehe SKILL.md.
    """
    for label in labels:
        if label.lower() in known_slugs:
            return label.lower()
    return None
