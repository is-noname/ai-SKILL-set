#!/usr/bin/env python3
"""Misst den realen Token-Verbrauch einer Claude-Code-Projekthistorie.

Liest die JSONL-Transcripts unter ~/.claude/projects/<projekt-slug>/ und
liefert Kennzahlen, aus denen sich Tokenfresser belegen lassen:
Verbrauch pro Tool, Wiederholungen, Cache-Quote, Subagent-Kosten.

Nutzung:
    python3 analyze_transcript.py                    # aktuelles Projekt, alle Sessions
    python3 analyze_transcript.py --project /pfad    # anderes Projekt
    python3 analyze_transcript.py --sessions 5       # nur die 5 juengsten Sessions
    python3 analyze_transcript.py --session <uuid>   # nur diese eine Session
    python3 analyze_transcript.py --since 2026-08-14 # nur Eintraege ab diesem Zeitpunkt
    python3 analyze_transcript.py --json             # Rohdaten statt Report
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

CHARS_PER_TOKEN = 4  # grobe Schaetzung fuer Tool-Result-Payloads


def project_slug(path: Path) -> str:
    """Claude Code legt Transcripts unter einem pfadbasierten Slug ab."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path.resolve()))


def find_transcripts(project: Path, limit: int | None, session: str | None = None) -> list[Path]:
    base = Path.home() / ".claude" / "projects" / project_slug(project)
    if not base.is_dir():
        return []
    if session:
        one = base / f"{session}.jsonl"
        return [one] if one.is_file() else []
    files = sorted(base.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit] if limit else files


def read_entries(files: list[Path], since: str | None = None,
                 until: str | None = None) -> Iterator[dict[str, Any]]:
    """Liest die Eintraege; since/until vergleichen das ISO-Feld `timestamp` als Praefix."""
    for f in files:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since or until:
                    ts = str(entry.get("timestamp") or "")
                    if not ts or (since and ts < since) or (until and ts > until):
                        continue
                yield entry


def content_len(content: Any) -> int:
    """Zeichenlaenge eines Message-Content-Felds, egal ob str oder Blockliste."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, str):
                total += len(block)
            elif isinstance(block, dict):
                total += len(json.dumps(block.get("content", block), ensure_ascii=False))
        return total
    if isinstance(content, dict):
        return len(json.dumps(content, ensure_ascii=False))
    return 0


def call_label(name: str, params: dict[str, Any]) -> str:
    """Kurzer, gruppierbarer Bezeichner fuer einen Tool-Call."""
    if name in ("Read", "Edit", "Write", "NotebookEdit"):
        return str(params.get("file_path", "?"))
    if name == "Bash":
        cmd = str(params.get("command", "")).strip().replace("\n", " ")
        return cmd[:120]
    if name in ("Grep", "Glob"):
        return f"{params.get('pattern', '?')} @ {params.get('path', '.')}"
    if name == "Agent":
        return f"{params.get('subagent_type', 'general-purpose')}: {params.get('description', '')}"
    if name == "Skill":
        return str(params.get("skill", "?"))
    return json.dumps(params, ensure_ascii=False)[:120]


def analyze(files: list[Path], since: str | None = None, until: str | None = None) -> dict[str, Any]:
    usage_by_request: dict[str, dict[str, int]] = {}
    tool_calls: dict[str, tuple[str, str, bool]] = {}  # tool_use_id -> (tool, label, sidechain)
    result_chars: dict[str, int] = defaultdict(int)  # tool_use_id -> chars
    calls_per_tool: Counter[str] = Counter()
    label_counts: dict[str, Counter[str]] = defaultdict(Counter)
    skills_used: Counter[str] = Counter()
    sidechain_output = 0

    for entry in read_entries(files, since, until):
        msg = entry.get("message")
        sidechain = bool(entry.get("isSidechain"))

        if entry.get("type") == "assistant" and isinstance(msg, dict):
            usage = msg.get("usage") or {}
            req = entry.get("requestId") or entry.get("uuid") or ""
            if usage and req not in usage_by_request:
                usage_by_request[req] = {
                    "input": int(usage.get("input_tokens") or 0),
                    "cache_read": int(usage.get("cache_read_input_tokens") or 0),
                    "cache_creation": int(usage.get("cache_creation_input_tokens") or 0),
                    "output": int(usage.get("output_tokens") or 0),
                    "sidechain": sidechain,
                }
                if sidechain:
                    sidechain_output += int(usage.get("output_tokens") or 0)
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    params = block.get("input") or {}
                    label = call_label(name, params if isinstance(params, dict) else {})
                    tool_calls[block.get("id", "")] = (name, label, sidechain)
                    calls_per_tool[name] += 1
                    label_counts[name][label] += 1
                    if name == "Skill" and isinstance(params, dict):
                        skills_used[str(params.get("skill", "?"))] += 1

        elif entry.get("type") == "user" and isinstance(msg, dict):
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tid = block.get("tool_use_id", "")
                    result_chars[tid] += content_len(block.get("content"))

    # Aggregation
    totals = {"input": 0, "cache_read": 0, "cache_creation": 0, "output": 0}
    for u in usage_by_request.values():
        for k in totals:
            totals[k] += u[k]

    tokens_per_tool: Counter[str] = Counter()
    per_call: list[dict[str, Any]] = []
    for tid, (name, label, sidechain) in tool_calls.items():
        est = result_chars.get(tid, 0) // CHARS_PER_TOKEN
        tokens_per_tool[name] += est
        per_call.append({"tool": name, "label": label, "tokens": est, "sidechain": sidechain})
    per_call.sort(key=lambda c: c["tokens"], reverse=True)

    repeats = []
    for name, labels in label_counts.items():
        for label, count in labels.items():
            if count > 1 and name in ("Read", "Bash", "Grep", "Glob"):
                cost = sum(c["tokens"] for c in per_call if c["tool"] == name and c["label"] == label)
                repeats.append({"tool": name, "label": label, "count": count, "tokens": cost})
    repeats.sort(key=lambda r: r["tokens"], reverse=True)

    cached = totals["cache_read"]
    fresh = totals["input"] + totals["cache_creation"]
    return {
        "sessions": len(files),
        "requests": len(usage_by_request),
        "totals": totals,
        "cache_hit_rate": round(cached / (cached + fresh), 3) if (cached + fresh) else 0.0,
        "calls_per_tool": dict(calls_per_tool.most_common()),
        "tokens_per_tool": dict(tokens_per_tool.most_common()),
        "top_calls": per_call[:20],
        "repeats": repeats[:20],
        "skills_used": dict(skills_used.most_common()),
        "subagent_output_tokens": sidechain_output,
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=os.getcwd(), help="Projektpfad (Default: cwd)")
    ap.add_argument("--sessions", type=int, default=None, help="nur die N juengsten Sessions")
    ap.add_argument("--session", default=None, help="nur diese Session-ID")
    ap.add_argument("--since", default=None, help="nur Eintraege ab diesem ISO-Zeitpunkt")
    ap.add_argument("--until", default=None, help="nur Eintraege bis zu diesem ISO-Zeitpunkt")
    ap.add_argument("--json", action="store_true", help="Rohdaten als JSON ausgeben")
    args = ap.parse_args()

    project = Path(args.project)
    files = find_transcripts(project, args.sessions, args.session)
    if not files:
        print(
            f"Keine Transcripts fuer {project} gefunden "
            f"(erwartet: ~/.claude/projects/{project_slug(project)}/*.jsonl).\n"
            "Ohne Historie laeuft die Analyse rein statisch weiter."
        )
        return 1

    data = analyze(files, args.since, args.until)
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
