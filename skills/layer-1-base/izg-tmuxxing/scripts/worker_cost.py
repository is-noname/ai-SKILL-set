#!/usr/bin/env python3
"""Tokenverbrauch eines tmuxx-Workers aus dessen Session-Store lesen.

Claude: ~/.claude/projects/<slug-des-workdir>/<session-id>.jsonl (usage je Message)
Vibe:   ~/.vibe/logs/session/session_*/meta.json (stats-Block)

Gibt eine Zeile pro Modell aus plus eine Summenzeile - Rohdaten fuer die
Tokennutzungsbewertung, keine Preisrechnung.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _since(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


def _newest(paths: list[Path], since: float) -> Path | None:
    fresh = [p for p in paths if p.stat().st_mtime >= since]
    return max(fresh or paths, key=lambda p: p.stat().st_mtime, default=None)


def claude_usage(workdir: Path, since: float, session: str | None) -> dict[str, dict[str, int]]:
    slug = str(workdir.resolve()).replace("/", "-")
    proj = Path.home() / ".claude" / "projects" / slug
    if session:
        # Ohne feste Session-ID trifft "neuestes Transcript" den Orchestrator,
        # der sich denselben Projektordner teilt.
        transcript = proj / f"{session}.jsonl"
        if not transcript.is_file():
            raise SystemExit(f"kein Transcript fuer Session {session} unter {proj}")
    else:
        transcript = _newest(sorted(proj.glob("*.jsonl")), since) if proj.is_dir() else None
    if transcript is None:
        raise SystemExit(f"kein Claude-Transcript unter {proj}")
    totals: dict[str, dict[str, int]] = {}
    with transcript.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                msg = json.loads(line).get("message") or {}
            except json.JSONDecodeError:
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            bucket = totals.setdefault(msg.get("model", "?"), dict.fromkeys(FIELDS, 0))
            for field in FIELDS:
                bucket[field] += int(usage.get(field) or 0)
    print(f"# {transcript}")
    return totals


def vibe_usage(workdir: Path, since: float) -> dict[str, dict[str, int]]:
    root = Path.home() / ".vibe" / "logs" / "session"
    target = str(workdir.resolve())
    metas = [m for m in root.glob("session_*/meta.json")
             if _workdir_of(m) == target] if root.is_dir() else []
    meta = _newest(metas, since)
    if meta is None:
        raise SystemExit(f"keine Vibe-Session fuer {target} unter {root}")
    stats = json.loads(meta.read_text(encoding="utf-8")).get("stats") or {}
    print(f"# {meta}")
    return {"vibe": {
        "input_tokens": int(stats.get("session_prompt_tokens") or 0),
        "output_tokens": int(stats.get("session_completion_tokens") or 0),
        "cache_read_input_tokens": int(stats.get("session_cached_tokens") or 0),
        "cache_creation_input_tokens": 0,
    }}


def _workdir_of(meta: Path) -> str | None:
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return (data.get("environment") or {}).get("working_directory")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", default="claude")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--since", default=None)
    ap.add_argument("--session", default=None, help="Claude sessionId (aus claude agents --json)")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    since = _since(args.since)
    totals = (vibe_usage(workdir, since) if args.worker == "vibe"
              else claude_usage(workdir, since, args.session))

    summe = dict.fromkeys(FIELDS, 0)
    print(f"{'modell':<28} {'input':>9} {'output':>9} {'cache_read':>11} {'cache_write':>11}")
    for model, bucket in sorted(totals.items()):
        print(f"{model:<28} {bucket['input_tokens']:>9} {bucket['output_tokens']:>9} "
              f"{bucket['cache_read_input_tokens']:>11} {bucket['cache_creation_input_tokens']:>11}")
        for field in FIELDS:
            summe[field] += bucket[field]
    print(f"{'SUMME':<28} {summe['input_tokens']:>9} {summe['output_tokens']:>9} "
          f"{summe['cache_read_input_tokens']:>11} {summe['cache_creation_input_tokens']:>11}")


if __name__ == "__main__":
    main()
