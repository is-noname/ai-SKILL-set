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

Der zweite Abschnitt (IZG-T-156) stellt das stueckweise Lesen dem Voll-Read
gegenueber: je (Session, Datei) mit mindestens zwei Teil-Reads die Summe der
Scheiben gegen die Kosten eines Voll-Reads, dazu die durch ueberlappende
Zeilenbereiche doppelt gelesenen Tokens. Wo die Datei heute fehlt oder kuerzer
ist als damals gelesen, wird der Voll-Read aus der Tokendichte der Scheiben
hochgerechnet und getrennt ausgewiesen.

Nutzung:
    python3 scripts/read_dedupe_report.py                    # alles
    python3 scripts/read_dedupe_report.py --since 2026-08-17 # ab Datum
    python3 scripts/read_dedupe_report.py --top 10           # teuerste Dateien
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

CHARS_PER_TOKEN = 4
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
LINE_NO_RE = re.compile(r"^\s*(\d+)\t", re.MULTILINE)


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


def line_range(text: str) -> tuple[int, int] | None:
    """Erste und letzte Zeilennummer aus einem Read-Ergebnis (cat -n-Format).

    Der Read gibt jede Zeile als "<nummer>\\t<inhalt>" aus. Aus dem tatsaechlichen
    Ergebnis gelesen ist der Bereich verlaesslicher als offset/limit, weil ein
    limit ueber das Dateiende hinaus dort nicht sichtbar waere.
    """
    nums = LINE_NO_RE.findall(text)
    if not nums:
        return None
    values = [int(n) for n in nums]
    return min(values), max(values)


def result_info(entry: dict) -> dict[str, tuple[int, tuple[int, int] | None]]:
    """tool_use_id -> (Zeichenlaenge, Zeilenbereich) aus einer user-Nachricht."""
    out: dict[str, tuple[int, tuple[int, int] | None]] = {}
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
        out[block.get("tool_use_id", "")] = (len(text), line_range(text))
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
        # (Session, Datei) -> Scheiben als (Tokens, erste Zeile, letzte Zeile)
        self.slices: dict[tuple[str, str], list[tuple[int, int, int]]] = defaultdict(list)
        self.slices_unranged = 0  # Teil-Reads ohne erkennbaren Zeilenbereich


def analyse_session(path: Path, stats: Stats, since: str | None) -> None:
    # Pfad -> True, solange seit dem letzten Voll-Read nichts geaendert wurde
    seen: dict[str, bool] = {}
    touched: set[str] = set()  # jeder gelesene Pfad, Teil-Reads eingeschlossen
    pending: dict[str, str] = {}  # tool_use_id -> Pfad, wartet auf sein Ergebnis
    repeat_ids: dict[str, str] = {}  # tool_use_id -> "covered" | "avoidable"
    partial_repeat_ids: set[str] = set()
    partial_ids: set[str] = set()  # jeder Teil-Read, fuer die Scheiben-Auswertung
    session = str(path)

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
                partial_ids.add(tuid)
                pending[tuid] = file_path  # Tokens und Zeilenbereich holt das Ergebnis
                # Zweite, weitere Sicht: Wiederholungen auf Pfad-Ebene, Teil-Reads
                # eingeschlossen. Der Hook deckt diesen Fall bewusst nicht ab, die
                # Zahl gehoert aber danebengestellt - sie ist die groessere.
                if file_path in touched:
                    stats.repeats_any += 1
                    partial_repeat_ids.add(tuid)
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

        for tuid, (length, rng) in result_info(entry).items():
            file_path = pending.pop(tuid, None)
            if file_path is None:
                continue
            tokens = length // CHARS_PER_TOKEN
            if tuid in partial_ids:
                partial_ids.discard(tuid)
                if rng is None:
                    stats.slices_unranged += 1
                else:
                    stats.slices[(session, file_path)].append((tokens, rng[0], rng[1]))
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


def full_read_tokens(file_path: str) -> tuple[int, int] | None:
    """(Tokens, Zeilen) eines Voll-Reads der Datei heute, None wenn sie fehlt.

    Der Read stellt jeder Zeile ihre Nummer und einen Tabulator voran; der
    Zuschlag ist mitgerechnet, sonst waere der Vergleich zugunsten des
    Voll-Reads verzerrt. Gemessen wird der heutige Stand der Datei - die
    Zeilenzahl geht mit zurueck, damit der Aufrufer erkennt, ob die Datei
    seit der Session geschrumpft ist und der Vergleich damit hinfaellig.
    """
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    n_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    prefix = sum(len(str(i)) + 1 for i in range(1, n_lines + 1))
    return (len(text) + prefix) // CHARS_PER_TOKEN, n_lines


def overlap_tokens(slices: list[tuple[int, int, int]]) -> int:
    """Tokens, die durch ueberlappende Scheiben mehrfach im Kontext landen.

    Je Scheibe wird eine gleichmaessige Tokendichte ueber ihre Zeilen
    angenommen. Eine Zeile, die k Scheiben abdecken, kostet (k-1)/k ihrer
    Gesamtdichte zu viel - unabhaengig davon, welche Scheibe man als die
    noetige ansieht.
    """
    density: dict[int, list[float]] = defaultdict(list)
    for tokens, lo, hi in slices:
        n_lines = max(hi - lo + 1, 1)
        per_line = tokens / n_lines
        for line in range(lo, hi + 1):
            density[line].append(per_line)
    excess = 0.0
    for values in density.values():
        k = len(values)
        if k > 1:
            excess += sum(values) * (k - 1) / k
    return round(excess)


def estimated_full_tokens(slices: list[tuple[int, int, int]]) -> int:
    """Voll-Read-Kosten von damals, geschaetzt aus den Scheiben selbst.

    Fuer Dateien, die es heute nicht mehr gibt oder die seither gekuerzt
    wurden, ist der heutige Stand kein Vergleichswert. Naeherung: mittlere
    Tokendichte der gelesenen Zeilen mal hoechste gelesene Zeilennummer. Das
    ist eine Untergrenze - die Datei kann ueber die letzte gelesene Zeile
    hinausgegangen sein, dann war der Voll-Read noch teurer.
    """
    tokens = sum(t for t, _, _ in slices)
    lines = sum(max(hi - lo + 1, 1) for _, lo, hi in slices)
    max_line = max(hi for _, _, hi in slices)
    return round(tokens / lines * max_line) if lines else 0


def count_table(rows: list[tuple], label: str) -> None:
    """Anteil der Datei je Scheibenzahl - rows wie in slice_report aufgebaut."""
    per_count: dict[int, list[float]] = defaultdict(list)
    for share, n_slices, *_ in rows:
        per_count[n_slices].append(share)
    print()
    print(label)
    print("| Scheiben | Faelle | Median Anteil der Datei | teurer als Voll-Read |")
    print("|---:|---:|---:|---:|")
    for n_slices in sorted(per_count):
        shares = sorted(per_count[n_slices])
        median = shares[len(shares) // 2]
        worse = sum(1 for s in shares if s >= 1.0)
        print(f"| {n_slices} | {len(shares)} | {median * 100:.0f} % | "
              f"{worse} ({pct(worse, len(shares))}) |")


def slice_report(stats: Stats, top: int) -> None:
    """Teil-Reads je (Session, Datei) gegen den Voll-Read stellen (IZG-T-156)."""
    groups = {key: sl for key, sl in stats.slices.items() if len(sl) >= 2}
    print()
    print("## Stueckweises Lesen - Teil-Reads gegen Voll-Read (IZG-T-156)")
    print()
    if not groups:
        print("Keine (Session, Datei) mit mindestens zwei Teil-Reads.")
        return

    full_cache: dict[str, tuple[int, int] | None] = {}
    rows = []  # (Anteil, Scheiben, Summe, Voll, Ueberlappung, Datei)
    missing = []  # Datei existiert heute nicht mehr
    shrunk = []  # Datei ist seit der Session kuerzer geworden - nicht vergleichbar
    overlap_cases = 0
    overlap_sum = 0
    for (_session, file_path), sl in groups.items():
        total = sum(t for t, _, _ in sl)
        over = overlap_tokens(sl)
        if over:
            overlap_cases += 1
            overlap_sum += over
        if file_path not in full_cache:
            full_cache[file_path] = full_read_tokens(file_path)
        info = full_cache[file_path]
        est = estimated_full_tokens(sl)
        bucket = None
        if info is None or info[0] == 0:
            bucket = missing
        elif max(hi for _, _, hi in sl) > info[1]:
            # Damals wurden Zeilen gelesen, die es heute nicht mehr gibt - der
            # heutige Voll-Read ist dann kein gueltiger Vergleichswert.
            bucket = shrunk
        if bucket is not None:
            bucket.append((total / est if est else 0.0, len(sl), total, est,
                           over, file_path))
            continue
        full = info[0]
        rows.append((total / full, len(sl), total, full, over, file_path))

    estimated = missing + shrunk
    print(f"(Session, Datei) mit >= 2 Teil-Reads: {len(groups):,} | "
          f"am heutigen Dateistand gemessen: {len(rows):,} | "
          f"geschaetzt (Datei fehlt: {len(missing):,}, seither gekuerzt: "
          f"{len(shrunk):,}): {len(estimated):,}")
    if stats.slices_unranged:
        print(f"Teil-Reads ohne erkennbaren Zeilenbereich (nicht gewertet): "
              f"{stats.slices_unranged:,}")
    print()
    print(f"Ueberlappende Faelle: {overlap_cases:,} | doppelt gelesen: "
          f"{overlap_sum:,} Tokens")

    count_table(rows, "Gemessen - Datei liegt heute unveraendert lang vor:")
    if estimated:
        count_table(estimated, "Geschaetzt - Voll-Read aus der Tokendichte der "
                               "Scheiben hochgerechnet (Untergrenze):")

    for label, bucket in (("gemessen", rows), ("geschaetzt", estimated)):
        worse = sorted((r for r in bucket if r[0] >= 1.0), reverse=True)
        print()
        print(f"Teurer als ein Voll-Read ({label}): {len(worse):,} von "
              f"{len(bucket):,} ({pct(len(worse), len(bucket))})")
        if top and worse:
            print()
            print("| Datei | Scheiben | Teil-Reads | Voll-Read | Anteil | Ueberlappung |")
            print("|---|---:|---:|---:|---:|---:|")
            for share, n_slices, total, full, over, file_path in worse[:top]:
                short = "/".join(Path(file_path).parts[-3:])
                print(f"| `{short}` | {n_slices} | {total:,} | {full:,} | "
                      f"{share * 100:.0f} % | {over:,} |")


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

    slice_report(stats, args.top)


if __name__ == "__main__":
    main()
