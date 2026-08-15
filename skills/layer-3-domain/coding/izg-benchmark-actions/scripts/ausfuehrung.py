#!/usr/bin/env python3
"""Der Adapter auf die echte Welt - Shell, `claude -p` und das Transcript auf der Platte.

Alles, was Geld kostet oder Dateien anfasst, liegt hier: der Aufruf der CLI, das Lesen
des Transcripts und die Verbuchung seines Verbrauchs ueber die Gewichte. `messlauf.fahre()`
kennt davon nichts - es bekommt eine `Ausfuehrung` hereingereicht und ruft drei Methoden.
Im Betrieb ist das `ClaudeAusfuehrung`, im Test ein Fake.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import messlauf
import runs
import transcript


def cli_version() -> str | None:
    """Version der Claude-CLI - ein stiller Preistreiber zwischen zwei Messrunden."""
    try:
        proc = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def measure_session(project: Path, session_id: str) -> dict[str, Any]:
    """Liest ein einzelnes Transcript und verbucht seinen Verbrauch ueber runs.WEIGHTS."""
    path = transcript.transcript_path(project, session_id)
    su = transcript.read_session(path, session_id)

    cached = su.usage["cache_read"]
    fresh = su.usage["input"] + su.usage["cache_creation"]
    return {
        "session_id": su.session_id,
        "requests": su.requests,
        "usage": su.usage,
        "weighted_tokens": round(sum(su.usage[k] * w for k, w in runs.WEIGHTS.items())),
        "raw_tokens": sum(su.usage.values()),
        "cache_hit_rate": round(cached / (cached + fresh), 3) if (cached + fresh) else 0.0,
        "tool_calls": su.tool_calls,
        "tool_result_tokens": su.tool_result_tokens,
        "skills_used": su.skills_used,
        "subagent_output_tokens": su.subagent_output_tokens,
        "first_timestamp": su.first_timestamp,
        "last_timestamp": su.last_timestamp,
    }


def execute_run(prompt: str, project: Path, session_id: str, model: str | None,
                permission_mode: str, timeout: int) -> dict[str, Any]:
    """Startet einen Headless-Lauf mit fester Session-ID."""
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--session-id", session_id, "--permission-mode", permission_mode]
    if model:
        cmd += ["--model", model]

    started = time.time()
    proc = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True, timeout=timeout)
    duration = round(time.time() - started, 1)

    payload: dict[str, Any] = {}
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {}
    return {
        "duration_s": duration,
        "exit_code": proc.returncode,
        "cost_usd": payload.get("total_cost_usd"),
        "num_turns": payload.get("num_turns"),
        "cli_subtype": payload.get("subtype"),
        "stderr_tail": proc.stderr.strip()[-400:] or None,
    }


class ClaudeAusfuehrung:
    """Der einzige Teil des Messlaufs, der Geld kostet - und der einzige, den der Test ersetzt."""

    def schalte_um(self, setup: str, project: Path) -> None:
        subprocess.run(setup, shell=True, cwd=str(project), check=False)

    def starte(self, auftrag: messlauf.Laufauftrag, session_id: str) -> dict[str, Any]:
        return execute_run(auftrag.prompt, auftrag.project, session_id, auftrag.model,
                           auftrag.permission_mode, auftrag.timeout)

    def miss(self, project: Path, session_id: str) -> dict[str, Any]:
        return measure_session(project, session_id)
