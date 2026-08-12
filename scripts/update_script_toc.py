#!/usr/bin/env python3
"""Pflegt das Kopf-Inhaltsverzeichnis (Funktionsname + Zeilennummer) in Shell-Skripten.

Sucht Top-Level-Funktionsdefinitionen (`name() {`) und schreibt/aktualisiert einen
markierten Block zwischen `# --- Inhaltsverzeichnis (auto) ---` und
`# --- Ende Inhaltsverzeichnis ---`. Fehlt der Block, wird er direkt nach dem
Kopfkommentar (vor der ersten Nicht-Kommentar-Zeile) eingefuegt.

Usage:
  update_script_toc.py <script.sh> [<script.sh> ...]       # schreibt/aktualisiert
  update_script_toc.py --check <script.sh> [...]           # exit 1 bei Drift, keine Schreibung
"""
import re
import sys

START = "# --- Inhaltsverzeichnis (auto) ---"
END = "# --- Ende Inhaltsverzeichnis ---"
FUNC_RE = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\(\)\s*\{')


def find_functions(lines: list[str]) -> list[tuple[str, int]]:
    entries = []
    for i, line in enumerate(lines, start=1):
        m = FUNC_RE.match(line)
        if m:
            entries.append((m.group(1), i))
    return entries


def render_toc(entries: list[tuple[str, int]], line_offset: int) -> list[str]:
    if not entries:
        return []
    width = max(len(name) for name, _ in entries)
    body = [f"#   {name.ljust(width)}  Zeile {ln + line_offset}" for name, ln in entries]
    return [START, "# Von update_script_toc.py generiert — nicht von Hand pflegen."] + body + [END]


def strip_existing_toc(lines: list[str]) -> tuple[list[str], int]:
    try:
        start_i = next(i for i, l in enumerate(lines) if l.rstrip() == START)
        end_i = next(i for i, l in enumerate(lines) if l.rstrip() == END)
    except StopIteration:
        return lines, -1
    after = end_i + 1
    if after < len(lines) and lines[after].strip() == "":
        after += 1
    return lines[:start_i] + lines[after:], start_i


def insert_point(lines: list[str]) -> int:
    i = 0
    if i < len(lines) and lines[i].startswith("#!"):
        i += 1
    while i < len(lines) and (lines[i].startswith("#") or lines[i].strip() == ""):
        i += 1
    return i


def process(path: str, check: bool) -> bool:
    with open(path) as f:
        raw = f.read()
    lines = raw.splitlines()

    # Funktionen im Skript ohne TOC-Block suchen, damit Referenz-Zeilennummern stimmen.
    without_toc, existing_at = strip_existing_toc(lines)
    entries = find_functions(without_toc)
    if not entries:
        return True

    insert_at = existing_at if existing_at >= 0 else insert_point(without_toc)
    # Block wird bei insert_at eingefuegt (len(toc)+1 Zeilen) - alles ab dort
    # verschiebt sich im Endergebnis entsprechend nach unten.
    block_len_placeholder = len(render_toc(entries, 0)) + 1
    shifted = [(name, ln + block_len_placeholder if ln > insert_at else ln) for name, ln in entries]
    toc = render_toc(shifted, 0)

    new_lines = without_toc[:insert_at] + toc + [""] + without_toc[insert_at:]
    new_content = "\n".join(new_lines) + "\n"

    if new_content == raw:
        return True
    if check:
        print(f"[update_script_toc] {path}: Inhaltsverzeichnis veraltet.", file=sys.stderr)
        return False
    with open(path, "w") as f:
        f.write(new_content)
    print(f"[update_script_toc] {path}: Inhaltsverzeichnis aktualisiert.")
    return True


def main() -> int:
    args = sys.argv[1:]
    check = "--check" in args
    paths = [a for a in args if a != "--check"]
    if not paths:
        print(__doc__, file=sys.stderr)
        return 2
    ok = True
    for path in paths:
        if not process(path, check):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
