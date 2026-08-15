#!/usr/bin/env python3
"""Misst den realen Token-Verbrauch einer Claude-Code-Projekthistorie.

Liest die JSONL-Transcripts unter ~/.claude/projects/<projekt-slug>/ und
liefert Kennzahlen, aus denen sich Tokenfresser belegen lassen:
Verbrauch pro Tool, Wiederholungen, Cache-Quote, Subagent-Kosten.

Das Formatwissen ueber das Transcript selbst (Slug, Parsing, Entdopplung,
Paarung, content-Gestalten) liegt im Skill `izg-transcript-reader`
(Dependency). Hier bleibt nur die Auswertung: Findings, Redundanzzaehlung,
Report-Rendering.

Nutzung:
    python3 analyze_transcript.py                    # aktuelles Projekt, alle Sessions
    python3 analyze_transcript.py --project /pfad    # anderes Projekt
    python3 analyze_transcript.py --sessions 5       # nur die 5 juengsten Sessions
    python3 analyze_transcript.py --json             # Rohdaten statt Report
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


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

from render import render_html  # noqa: E402

CACHE_HIT_RATE_THRESHOLD = 0.85  # darunter deutet auf Cache-Bruch (IZG-T-137)
REDUNDANZ_COUNT_THRESHOLD = 3  # ab dieser Wiederholungszahl gilt ein Aufruf als redundant

# Re-Exports des Formatwissens - Tests und Aufrufer greifen ueber dieses Modul zu.
_t = _locate.re_export(globals(), [
    "CHARS_PER_TOKEN",
    "project_slug",
    "find_transcripts",
    "content_len",
    "call_label",
])


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


@dataclass
class Finding:
    signal: str
    value: float | int
    evidence: str
    confidence: str


@dataclass
class Measurement:
    """Typisiertes Ergebnis von `analyze()` - kein rohes Dict.

    `repeats` traegt die volle, unslicete Liste (Grundlage fuer die
    Redundanz-Regel); die auf 20 Eintraege gekuerzte Fassung fuer den
    JSON-/Report-Output entsteht erst beim Serialisieren in `analyze()`.
    """

    sessions: int
    requests: int
    totals: dict[str, int]
    cache_hit_rate: float
    calls_per_tool: dict[str, int]
    tokens_per_tool: dict[str, int]
    top_calls: list[dict[str, Any]]
    repeats: list[dict[str, Any]]
    skills_used: dict[str, int]
    subagent_output_tokens: int
    findings: list[Finding] = field(default_factory=list)


def rule_cache_bruch(m: Measurement) -> Finding | None:
    fresh = m.totals["input"] + m.totals["cache_creation"]
    if (m.totals["cache_read"] + fresh) > 0 and m.cache_hit_rate < CACHE_HIT_RATE_THRESHOLD:
        return Finding(
            signal="cache-bruch",
            value=m.cache_hit_rate,
            evidence=f"Cache-Trefferquote {fmt_pct(m.cache_hit_rate)} ueber {m.sessions} Sessions",
            confidence="belegt",
        )
    return None


def rule_redundanz(m: Measurement) -> list[Finding]:
    findings = []
    for r in m.repeats:
        if r["count"] >= REDUNDANZ_COUNT_THRESHOLD:
            findings.append(Finding(
                signal="redundanz",
                value=r["count"],
                evidence=f"{r['tool']} `{r['label']}` {r['count']}x aufgerufen ({fmt(r['tokens'])} Tokens)",
                confidence="belegt",
            ))
    return findings


RULES = [rule_cache_bruch, rule_redundanz]


def compute_findings(measurement: Measurement) -> list[Finding]:
    """Zieht die Auswertungen, die SKILL.md bisher in Prosa verlangt hat."""
    findings: list[Finding] = []
    for rule in RULES:
        result = rule(measurement)
        if result is None:
            continue
        if isinstance(result, list):
            findings.extend(result)
        else:
            findings.append(result)
    return findings


def analyze(files: list[Path]) -> dict[str, Any]:
    parsed = _t.parse_entries(_t.read_entries(files))
    totals = _t.usage_totals(parsed.usage_by_request)

    per_call = _t.estimate_tool_tokens(parsed.tool_calls, parsed.result_chars)
    per_call.sort(key=lambda c: c["tokens"], reverse=True)

    tokens_per_tool: Counter[str] = Counter()
    for c in per_call:
        tokens_per_tool[c["tool"]] += c["tokens"]

    repeats = []
    for name, labels in parsed.label_counts.items():
        for label, count in labels.items():
            if count > 1 and name in ("Read", "Bash", "Grep", "Glob"):
                cost = sum(c["tokens"] for c in per_call if c["tool"] == name and c["label"] == label)
                repeats.append({"tool": name, "label": label, "count": count, "tokens": cost})
    repeats.sort(key=lambda r: r["tokens"], reverse=True)

    cached = totals["cache_read"]
    fresh = totals["input"] + totals["cache_creation"]
    cache_hit_rate = round(cached / (cached + fresh), 3) if (cached + fresh) else 0.0

    measurement = Measurement(
        sessions=len(files),
        requests=len(parsed.usage_by_request),
        totals=totals,
        cache_hit_rate=cache_hit_rate,
        calls_per_tool=dict(parsed.calls_per_tool.most_common()),
        tokens_per_tool=dict(tokens_per_tool.most_common()),
        top_calls=per_call[:20],
        repeats=repeats,
        skills_used=dict(parsed.skills_used.most_common()),
        subagent_output_tokens=parsed.sidechain_output_tokens,
    )
    measurement.findings = compute_findings(measurement)

    data = dataclasses.asdict(measurement)
    data["repeats"] = data["repeats"][:20]
    return data


def empty_data() -> dict[str, Any]:
    """analyze()-Shape fuer den Fall ohne Transcripts - traegt --html AC4."""
    return {
        "sessions": 0,
        "requests": 0,
        "totals": {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0},
        "cache_hit_rate": 0.0,
        "calls_per_tool": {},
        "tokens_per_tool": {},
        "top_calls": [],
        "repeats": [],
        "skills_used": {},
        "subagent_output_tokens": 0,
        "findings": [],
    }


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def report(data: dict[str, Any]) -> str:
    t = data["totals"]
    out = [
        f"# Token-Messung ({data['sessions']} Sessions, {data['requests']} Requests)",
        "",
        "## Gesamtverbrauch",
        "",
        "| Kennzahl | Tokens |",
        "|---|---:|",
        f"| Input (ungecacht) | {fmt(t['input'])} |",
        f"| Cache-Schreibvorgang | {fmt(t['cache_creation'])} |",
        f"| Cache-Treffer | {fmt(t['cache_read'])} |",
        f"| Output | {fmt(t['output'])} |",
        f"| Cache-Trefferquote | {data['cache_hit_rate'] * 100:.1f} % |",
        f"| Output aus Subagents | {fmt(data['subagent_output_tokens'])} |",
        "",
        "## Befunde",
        "",
        "| Signal | Wert | Evidenz | Vertrauen |",
        "|---|---:|---|---|",
    ]
    if data["findings"]:
        for f in data["findings"]:
            out.append(f"| {f['signal']} | {f['value']} | {f['evidence']} | {f['confidence']} |")
    else:
        out.append("| - | - | keine | - |")

    out += [
        "",
        "## Kontextlast pro Tool (geschaetzt aus Tool-Results)",
        "",
        "| Tool | Aufrufe | Tokens |",
        "|---|---:|---:|",
    ]
    for tool, tokens in data["tokens_per_tool"].items():
        out.append(f"| {tool} | {data['calls_per_tool'].get(tool, 0)} | {fmt(tokens)} |")

    out += ["", "## Teuerste Einzelaufrufe", "", "| Tokens | Tool | Aufruf |", "|---:|---|---|"]
    for c in data["top_calls"]:
        mark = " (Subagent)" if c["sidechain"] else ""
        out.append(f"| {fmt(c['tokens'])} | {c['tool']}{mark} | `{c['label']}` |")

    out += ["", "## Wiederholte Aufrufe (Kandidaten fuer Redundanz)", "",
            "| Wiederholungen | Tokens | Tool | Aufruf |", "|---:|---:|---|---|"]
    if data["repeats"]:
        for r in data["repeats"]:
            out.append(f"| {r['count']}x | {fmt(r['tokens'])} | {r['tool']} | `{r['label']}` |")
    else:
        out.append("| - | - | - | keine |")

    if data["skills_used"]:
        out += ["", "## Genutzte Skills", ""]
        out += [f"- {k}: {v}x" for k, v in data["skills_used"].items()]
    return "\n".join(out)


def _write_html(data: dict[str, Any], project: Path, html_arg: str) -> Path:
    project_name = project.resolve().name
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = render_html(data, project_name, generated_at)
    if html_arg:
        path = Path(html_arg)
    else:
        tmpdir = Path(os.environ.get("TMPDIR", "/tmp"))
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = tmpdir / f"token-review-{ts}.html"
    path.write_text(html, encoding="utf-8")
    return path


def main(base_dir: Path | None = None) -> int:
    """`base_dir` ersetzt in Tests ~/.claude/projects/<slug>/ - kein CLI-Flag,
    reiner Test-Seam (siehe find_transcripts)."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=os.getcwd(), help="Projektpfad (Default: cwd)")
    ap.add_argument("--sessions", type=int, default=None, help="nur die N juengsten Sessions")
    ap.add_argument("--json", action="store_true", help="Rohdaten als JSON ausgeben")
    ap.add_argument("--html", nargs="?", const="", default=None, metavar="PFAD",
                     help="HTML-Report schreiben (ohne Pfad: Temp-Verzeichnis)")
    args = ap.parse_args()

    project = Path(args.project)
    files = find_transcripts(project, args.sessions, base_dir=base_dir)
    if not files:
        print(
            f"Keine Transcripts fuer {project} gefunden "
            f"(erwartet: ~/.claude/projects/{project_slug(project)}/*.jsonl).\n"
            "Ohne Historie laeuft die Analyse rein statisch weiter."
        )
        if args.html is not None:
            print(_write_html(empty_data(), project, args.html))
        return 1

    data = analyze(files)
    if args.html is not None:
        print(_write_html(data, project, args.html))
    elif args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
