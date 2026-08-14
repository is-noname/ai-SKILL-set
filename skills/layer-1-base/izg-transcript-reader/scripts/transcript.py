#!/usr/bin/env python3
"""Liest Claude-Code-Transcripts (JSONL) und liefert ihren Verbrauch.

Kapselt das undokumentierte Transcript-Format: Projekt-Slug, Datei-Auffindung,
Zeilen-Parsing, usage-Entdopplung ueber requestId (Fallback uuid),
tool_use/tool_result-Paarung ueber Block-ID, isSidechain-Verbuchung, die drei
content-Gestalten (str/list/dict) und call_label (Formatwissen ueber
Tool-Parameter).

Aendert Claude Code das Format, bricht dieser Adapter sichtbar an einer Stelle,
nicht still an zwei.

Interface: transcript_path()/find_transcripts() zum Auffinden, read_session()
fuer eine einzelne Session, read_entries()/parse_entries() fuer Auswertungen
ueber mehrere Sessions (Filter, Gruppierung, Wiederholungszaehlung bleiben
beim aufrufenden Skill). Alles andere ist Detail.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

CHARS_PER_TOKEN = 4  # grobe Schaetzung fuer Tool-Result-Payloads

USAGE_KEYS = ("input", "cache_read", "cache_creation", "output")


@dataclass
class SessionUsage:
    """Typisierter Verbrauch einer einzelnen Session - kein rohes Dict."""

    session_id: str
    requests: int
    usage: dict[str, int]
    tool_calls: dict[str, int]
    tool_result_tokens: dict[str, int]
    skills_used: dict[str, int]
    subagent_output_tokens: int
    first_timestamp: str | None
    last_timestamp: str | None


@dataclass
class ParsedTranscript:
    """Rohe Bausteine aus einem Entry-Strom - Aggregation bleibt beim Aufrufer."""

    usage_by_request: dict[str, dict[str, int]] = field(default_factory=dict)
    tool_calls: dict[str, tuple[str, str, bool]] = field(default_factory=dict)
    result_chars: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    calls_per_tool: Counter[str] = field(default_factory=Counter)
    label_counts: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    skills_used: Counter[str] = field(default_factory=Counter)
    sidechain_output_tokens: int = 0
    timestamps: list[str] = field(default_factory=list)


def project_slug(path: Path) -> str:
    """Claude Code legt Transcripts unter einem pfadbasierten Slug ab."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path.resolve()))


def transcript_path(project: Path, session_id: str) -> Path:
    """Pfad, unter dem Claude Code das Transcript einer Session ablegt."""
    return Path.home() / ".claude" / "projects" / project_slug(project) / f"{session_id}.jsonl"


def find_transcripts(project: Path, limit: int | None, session: str | None = None,
                      base_dir: Path | None = None) -> list[Path]:
    """Findet Transcript-Dateien eines Projekts, juengste zuerst."""
    base = base_dir if base_dir is not None else \
        Path.home() / ".claude" / "projects" / project_slug(project)
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
    """Zeichenlaenge eines Message-Content-Felds, egal ob str, Blockliste oder Dict."""
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


def parse_entries(entries: Iterable[dict[str, Any]]) -> ParsedTranscript:
    """Liest einen Entry-Strom in die rohen Bausteine - keine Aggregation."""
    p = ParsedTranscript()

    for entry in entries:
        if entry.get("timestamp"):
            p.timestamps.append(str(entry["timestamp"]))

        msg = entry.get("message")
        if not isinstance(msg, dict):
            continue
        sidechain = bool(entry.get("isSidechain"))

        if entry.get("type") == "assistant":
            usage = msg.get("usage") or {}
            req = entry.get("requestId") or entry.get("uuid") or ""
            if usage and req not in p.usage_by_request:
                p.usage_by_request[req] = {
                    "input": int(usage.get("input_tokens") or 0),
                    "cache_read": int(usage.get("cache_read_input_tokens") or 0),
                    "cache_creation": int(usage.get("cache_creation_input_tokens") or 0),
                    "output": int(usage.get("output_tokens") or 0),
                }
                if sidechain:
                    p.sidechain_output_tokens += int(usage.get("output_tokens") or 0)
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = str(block.get("name", "?"))
                    params = block.get("input") or {}
                    label = call_label(name, params if isinstance(params, dict) else {})
                    p.tool_calls[str(block.get("id", ""))] = (name, label, sidechain)
                    p.calls_per_tool[name] += 1
                    p.label_counts[name][label] += 1
                    if name == "Skill" and isinstance(params, dict):
                        p.skills_used[str(params.get("skill", "?"))] += 1

        elif entry.get("type") == "user":
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tid = str(block.get("tool_use_id", ""))
                    p.result_chars[tid] += content_len(block.get("content"))

    return p


def usage_totals(usage_by_request: dict[str, dict[str, int]]) -> dict[str, int]:
    """Summiert die entdoppelten Usage-Eintraege ueber alle Requests."""
    totals = {k: 0 for k in USAGE_KEYS}
    for u in usage_by_request.values():
        for k in totals:
            totals[k] += u[k]
    return totals


def estimate_tool_tokens(tool_calls: dict[str, tuple[str, str, bool]],
                          result_chars: dict[str, int]) -> list[dict[str, Any]]:
    """Schaetzt Tokens je Tool-Aufruf aus der Zeichenlaenge seines Tool-Results."""
    per_call = []
    for tid, (name, label, sidechain) in tool_calls.items():
        est = result_chars.get(tid, 0) // CHARS_PER_TOKEN
        per_call.append({"tool": name, "label": label, "tokens": est, "sidechain": sidechain})
    return per_call


def read_session(path: Path, session_id: str) -> SessionUsage:
    """Liest ein Transcript von einem beliebigen Pfad und fasst seinen Verbrauch zusammen.

    Der Pfad ist ein Parameter statt intern aus HOME gebaut zu werden, damit Tests
    gegen eine Fixture-Datei laufen koennen, ohne HOME anzufassen.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Kein Transcript unter {path}")

    parsed = parse_entries(read_entries([path]))
    per_call = estimate_tool_tokens(parsed.tool_calls, parsed.result_chars)

    result_tokens: Counter[str] = Counter()
    for c in per_call:
        result_tokens[c["tool"]] += c["tokens"]

    return SessionUsage(
        session_id=session_id,
        requests=len(parsed.usage_by_request),
        usage=usage_totals(parsed.usage_by_request),
        tool_calls=dict(parsed.calls_per_tool.most_common()),
        tool_result_tokens=dict(result_tokens.most_common()),
        skills_used=dict(parsed.skills_used.most_common()),
        subagent_output_tokens=parsed.sidechain_output_tokens,
        first_timestamp=min(parsed.timestamps) if parsed.timestamps else None,
        last_timestamp=max(parsed.timestamps) if parsed.timestamps else None,
    )
