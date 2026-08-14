#!/usr/bin/env python3
"""Liest ein einzelnes Claude-Code-Transcript (JSONL) und liefert seinen Verbrauch.

Kapselt das undokumentierte Transcript-Format: Projekt-Slug, Zeilen-Parsing,
usage-Entdopplung ueber requestId (Fallback uuid), tool_use/tool_result-Paarung
ueber Block-ID, isSidechain und die drei content-Gestalten (str/list/dict).

Aendert Claude Code das Format, bricht dieser Adapter sichtbar an einer Stelle,
nicht still an zwei.

Interface: transcript_path() zum Auffinden, read_session() zum Einlesen. Beide
Funktionen sind das ganze oeffentliche Interface - alles andere ist Detail.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def _project_slug(path: Path) -> str:
    """Claude Code legt Transcripts unter einem pfadbasierten Slug ab."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path.resolve()))


def _content_len(content: Any) -> int:
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


def transcript_path(project: Path, session_id: str) -> Path:
    """Pfad, unter dem Claude Code das Transcript einer Session ablegt."""
    return Path.home() / ".claude" / "projects" / _project_slug(project) / f"{session_id}.jsonl"


def read_session(path: Path, session_id: str) -> SessionUsage:
    """Liest ein Transcript von einem beliebigen Pfad und fasst seinen Verbrauch zusammen.

    Der Pfad ist ein Parameter statt intern aus HOME gebaut zu werden, damit Tests
    gegen eine Fixture-Datei laufen koennen, ohne HOME anzufassen.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Kein Transcript unter {path}")

    usage_by_request: dict[str, dict[str, int]] = {}
    tool_names: dict[str, str] = {}
    tool_result_chars: Counter[str] = Counter()
    calls_per_tool: Counter[str] = Counter()
    skills_used: Counter[str] = Counter()
    sidechain_output = 0
    stamps: list[str] = []

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("timestamp"):
                stamps.append(str(entry["timestamp"]))
            msg = entry.get("message")
            if not isinstance(msg, dict):
                continue

            if entry.get("type") == "assistant":
                usage = msg.get("usage") or {}
                req = entry.get("requestId") or entry.get("uuid") or ""
                if usage and req not in usage_by_request:
                    usage_by_request[req] = {
                        "input": int(usage.get("input_tokens") or 0),
                        "cache_read": int(usage.get("cache_read_input_tokens") or 0),
                        "cache_creation": int(usage.get("cache_creation_input_tokens") or 0),
                        "output": int(usage.get("output_tokens") or 0),
                    }
                    if entry.get("isSidechain"):
                        sidechain_output += int(usage.get("output_tokens") or 0)
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        name = str(block.get("name", "?"))
                        calls_per_tool[name] += 1
                        tool_names[str(block.get("id", ""))] = name
                        params = block.get("input")
                        if name == "Skill" and isinstance(params, dict):
                            skills_used[str(params.get("skill", "?"))] += 1

            elif entry.get("type") == "user":
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tid = str(block.get("tool_use_id", ""))
                        tool_result_chars[tid] += _content_len(block.get("content"))

    usage = {k: 0 for k in USAGE_KEYS}
    for u in usage_by_request.values():
        for k in usage:
            usage[k] += u[k]

    result_tokens: Counter[str] = Counter()
    for tid, name in tool_names.items():
        result_tokens[name] += tool_result_chars.get(tid, 0) // CHARS_PER_TOKEN

    return SessionUsage(
        session_id=session_id,
        requests=len(usage_by_request),
        usage=usage,
        tool_calls=dict(calls_per_tool.most_common()),
        tool_result_tokens=dict(result_tokens.most_common()),
        skills_used=dict(skills_used.most_common()),
        subagent_output_tokens=sidechain_output,
        first_timestamp=min(stamps) if stamps else None,
        last_timestamp=max(stamps) if stamps else None,
    )
