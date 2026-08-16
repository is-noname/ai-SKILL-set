#!/usr/bin/env python3
"""Misst wiederholte Voll-Reads derselben Datei je Session (IZG-T-154/155).

Wertet die Claude-Code-Transcripts unter ~/.claude/projects/ aus und trennt
Wiederholungen in zwei Faelle:

  gedeckt     - zwischen den beiden Reads lag ein Edit/Write/NotebookEdit auf
                denselben Pfad, der Zweit-Read war also berechtigt
  vermeidbar  - keine Aenderung dazwischen, der Inhalt stand unveraendert im
                Kontext. Genau diesen Fall meldet read-dedupe-guard.sh.

Teil-Reads (offset oder limit) werden getrennt gezaehlt und markieren keinen
Voll-Read als Wiederholung. Tokens sind aus der Zeichenlaenge des Tool-Results
geschaetzt (~4 Zeichen/Token), nicht gemessen.

Nutzung:
    python3 scripts/read_dedupe_report.py                    # alles
    python3 scripts/read_dedupe_report.py --since 2026-08-17 # ab Datum
    python3 scripts/read_dedupe_report.py --top 10           # teuerste Dateien
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

CHARS_PER_TOKEN = 4
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def iter_entries(path: Path):
    """Liefert die JSON-Objekte einer Transcript-Datei, defekte Zeilen uebersprungen."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def result_length(entry: dict) -> dict[str, int]:
    """tool_use_id -> Zeichenlaenge des Ergebnisses, aus einer user-Nachricht."""
    out: dict[str, int] = {}
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return out
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        payload = block.get("content")
        if isinstance(payload, list):
            text = "".join(
                p.get("text", "") for p in payload if isinstance(p, dict)
            )
        else:
            text = payload if isinstance(payload, str) else ""
        out[block.get("tool_use_id", "")] = len(text)
    return out


def tool_calls(entry: dict):
    """(tool_use_id, name, input) je tool_use-Block einer assistant-Nachricht."""
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            yield block.get("id", ""), block.get("name", ""), block.get("input") or {}


class Stats:
    def __init__(self) -> None:
        self.reads = 0
        self.partial = 0
        self.repeats_covered = 0
        self.repeats_avoidable = 0
        self.tokens_total = 0
        self.tokens_covered = 0
        self.tokens_avoidable = 0
        self.repeats_any = 0
        self.tokens_any_repeat = 0
        self.per_file: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])


def analyse_session(path: Path, stats: Stats, since: str | None) -> None:
    # Pfad -> True, solange seit dem letzten Voll-Read nichts geaendert wurde
    seen: dict[str, bool] = {}
    touched: set[str] = set()  # jeder gelesene Pfad, Teil-Reads eingeschlossen
    pending: dict[str, str] = {}  # tool_use_id -> Pfad, wartet auf sein Ergebnis
    repeat_ids: dict[str, str] = {}  # tool_use_id -> "covered" | "avoidable"
    partial_repeat_ids: set[str] = set()

    for entry in iter_entries(path):
        ts = entry.get("timestamp") or ""
        if since and ts and ts[:10] < since:
            continue

        for tuid, name, tinput in tool_calls(entry):
            file_path = tinput.get("file_path")
            if not isinstance(file_path, str) or not file_path:
                continue
            if name in EDIT_TOOLS:
                # Nur entwerten, was schon gelesen wurde - ein Edit ohne vorherigen
                # Read darf den naechsten Read nicht zur Wiederholung machen.
                if file_path in seen:
                    seen[file_path] = False
                continue
            if name != "Read":
                continue
            if tinput.get("offset") is not None or tinput.get("limit") is not None:
                stats.partial += 1
                # Zweite, weitere Sicht: Wiederholungen auf Pfad-Ebene, Teil-Reads
                # eingeschlossen. Der Hook deckt diesen Fall bewusst nicht ab, die
                # Zahl gehoert aber danebengestellt - sie ist die groessere.
                if file_path in touched:
                    stats.repeats_any += 1
                    partial_repeat_ids.add(tuid)
                    pending[tuid] = file_path  # nur fuer die Token-Summe unten
                touched.add(file_path)
                continue
            if file_path in touched:
                stats.repeats_any += 1
            touched.add(file_path)
            stats.reads += 1
            pending[tuid] = file_path
            if file_path in seen:
                kind = "avoidable" if seen[file_path] else "covered"
                repeat_ids[tuid] = kind
                if kind == "avoidable":
                    stats.repeats_avoidable += 1
                else:
                    stats.repeats_covered += 1
            seen[file_path] = True

        for tuid, length in result_length(entry).items():
            file_path = pending.pop(tuid, None)
            if file_path is None:
                continue
            tokens = length // CHARS_PER_TOKEN
            if tuid in partial_repeat_ids:
                partial_repeat_ids.discard(tuid)
                stats.tokens_any_repeat += tokens
                continue  # Teil-Reads zaehlen nicht in die Voll-Read-Kontextlast
            stats.tokens_total += tokens
            kind = repeat_ids.pop(tuid, None)
            if kind:
                stats.tokens_any_repeat += tokens
            if kind == "avoidable":
                stats.tokens_avoidable += tokens
                row = stats.per_file[file_path]
                row[1] += 1
                row[2] += tokens
            elif kind == "covered":
                stats.tokens_covered += tokens
            row = stats.per_file[file_path]
            row[0] += 1


def pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f} %" if whole else "-"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--projects",
        default=str(Path.home() / ".claude" / "projects"),
        help="Wurzel der Transcripts (Default ~/.claude/projects)",
    )
    ap.add_argument("--since", help="nur Eintraege ab diesem Datum, YYYY-MM-DD")
    ap.add_argument("--top", type=int, default=6, help="teuerste Dateien anzeigen")
    args = ap.parse_args()

    files = sorted(Path(args.projects).rglob("*.jsonl"))
    stats = Stats()
    for path in files:
        analyse_session(path, stats, args.since)

    repeats = stats.repeats_covered + stats.repeats_avoidable
    tokens_repeat = stats.tokens_covered + stats.tokens_avoidable

    print(f"Transcripts: {len(files)}" + (f" (ab {args.since})" if args.since else ""))
    print()
    print("| Kennzahl | Wert |")
    print("|---|---:|")
    print(f"| Voll-Reads gesamt | {stats.reads:,} |")
    print(f"| Teil-Reads (offset/limit) | {stats.partial:,} |")
    print(f"| Wiederholungen | {repeats:,} ({pct(repeats, stats.reads)}) |")
    print(f"| davon gedeckt (Edit dazwischen) | {stats.repeats_covered:,} "
          f"({pct(stats.repeats_covered, repeats)}) |")
    print(f"| davon vermeidbar | {stats.repeats_avoidable:,} "
          f"({pct(stats.repeats_avoidable, repeats)}) |")
    print(f"| Read-Kontextlast gesamt | {stats.tokens_total:,} Tokens |")
    print(f"| davon redundant | {tokens_repeat:,} ({pct(tokens_repeat, stats.tokens_total)}) |")
    print(f"| davon vermeidbar | {stats.tokens_avoidable:,} Tokens |")
    print()
    print("Weitere Sicht - Wiederholungen auf Pfad-Ebene, Teil-Reads eingeschlossen")
    print("(vom Hook bewusst nicht abgedeckt):")
    print(f"  Wiederholungen: {stats.repeats_any:,} | Tokens: {stats.tokens_any_repeat:,}")

    if args.top:
        rows = sorted(stats.per_file.items(), key=lambda kv: -kv[1][2])[: args.top]
        rows = [r for r in rows if r[1][1]]
        if rows:
            print()
            print("| Datei | Reads | vermeidbare Wdh. | Tokens |")
            print("|---|---:|---:|---:|")
            for file_path, (reads, rep, tok) in rows:
                short = "/".join(Path(file_path).parts[-3:])
                print(f"| `{short}` | {reads} | {rep} | {tok:,} |")


if __name__ == "__main__":
    main()
