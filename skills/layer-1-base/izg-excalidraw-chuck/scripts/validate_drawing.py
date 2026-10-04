#!/usr/bin/env python3
"""Validiert eine Excalidraw-Markdown-Datei fuers obsidian-excalidraw-plugin.

Extrahiert den JSON- oder compressed-json-Fence aus '## Drawing' und prueft,
ob rohes JSON syntaktisch gueltig ist. compressed-json-Fences werden nur
erkannt, nicht dekomprimiert (dafuer gibt es kein GUI hier) - dann vor dem
naechsten Edit den Rohzustand aus der eigenen letzten Write-Version nehmen,
nicht aus der Datei zurueckdekomprimieren.

Usage:
    scripts/validate_drawing.py <pfad-zur-datei.md>
"""

import json
import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_drawing.py <pfad-zur-datei.md>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    content = path.read_text(encoding="utf-8")

    if "excalidraw-plugin: parsed" not in content:
        print("FEHLER: Frontmatter 'excalidraw-plugin: parsed' fehlt.")
        return 1

    compressed_match = re.search(r"```compressed-json\n(.*?)\n```", content, re.S)
    if compressed_match:
        print("Datei enthaelt bereits ```compressed-json (von Obsidian selbst erzeugt).")
        print("Das ist normal nach dem ersten Oeffnen in Obsidian - kein Fehler.")
        return 0

    json_match = re.search(r"```json\n(.*?)\n```", content, re.S)
    if not json_match:
        print("FEHLER: Weder ```json noch ```compressed-json Fence unter '## Drawing' gefunden.")
        return 1

    try:
        data = json.loads(json_match.group(1))
    except json.JSONDecodeError as exc:
        print(f"FEHLER: JSON ungueltig: {exc}")
        return 1

    for key in ("type", "version", "elements", "appState", "files"):
        if key not in data:
            print(f"FEHLER: Top-Level-Feld '{key}' fehlt.")
            return 1

    ids = set()
    for i, el in enumerate(data["elements"]):
        for key in ("id", "type", "x", "y", "width", "height"):
            if key not in el:
                print(f"FEHLER: Element {i} ({el.get('id', '?')}) fehlt Feld '{key}'.")
                return 1
        if el["id"] in ids:
            print(f"FEHLER: Doppelte id '{el['id']}'.")
            return 1
        ids.add(el["id"])

    print(f"OK: {len(data['elements'])} Elemente, JSON valide, keine doppelten IDs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
