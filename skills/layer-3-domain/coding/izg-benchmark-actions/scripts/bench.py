#!/usr/bin/env python3
"""Misst und vergleicht die Kosten einzelner Ablaeufe (Skills, Workflows, Prompts).

Anders als eine Verbrauchsanalyse ueber ein ganzes Projekt misst dieses Skript
**einzelne Laeufe**: jeder Lauf bekommt eine eigene Session-ID, wird isoliert
ausgefuehrt und einzeln verbucht. Aus mehreren Laeufen pro Variante entsteht ein
Vergleich mit Median und Spanne.

Nutzung:
    bench.py run --task t1 --variant mit-skill --prompt-file aufgabe.md --repeat 3
    bench.py measure --task t1 --variant manuell --session-id <uuid>
    bench.py judge --task t1 --variant mit-skill --run 1 --outcome ok
    bench.py compare --baseline ohne-skill

Alle Laufdaten liegen als JSON unter --out (Default: <tmp>/izg-bench).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import tempfile
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHARS_PER_TOKEN = 4  # grobe Schaetzung fuer Tool-Result-Payloads

# Gewichte in Input-Token-Aequivalenten, angelehnt an die Anthropic-Preisstruktur.
# Ein Lauf, der den Cache schont, sieht in rohen Summen sonst schlechter aus als er ist.
WEIGHTS = {"input": 1.0, "cache_creation": 1.25, "cache_read": 0.1, "output": 5.0}

OUTCOMES = ("ok", "partial", "fail", "unset")


# --------------------------------------------------------------------------- Pfade


def project_slug(path: Path) -> str:
    """Claude Code legt Transcripts unter einem pfadbasierten Slug ab."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path.resolve()))


def transcript_path(project: Path, session_id: str) -> Path:
    return Path.home() / ".claude" / "projects" / project_slug(project) / f"{session_id}.jsonl"


def default_out() -> Path:
    return Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "izg-bench"


def record_path(out: Path, task: str, variant: str, run: int) -> Path:
    safe = lambda s: re.sub(r"[^a-zA-Z0-9_-]", "-", s)  # noqa: E731
    return out / f"{safe(task)}__{safe(variant)}__{run:02d}.json"


# ----------------------------------------------------------------------- Messung


def content_len(content: Any) -> int:
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


def measure_session(project: Path, session_id: str) -> dict[str, Any]:
    """Liest ein einzelnes Transcript und verbucht seinen Verbrauch."""
    path = transcript_path(project, session_id)
    if not path.is_file():
        raise FileNotFoundError(f"Kein Transcript unter {path}")

    usage_by_request: dict[str, dict[str, int]] = {}
    tool_calls: dict[str, str] = {}
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
                        tool_calls[str(block.get("id", ""))] = name
                        params = block.get("input")
                        if name == "Skill" and isinstance(params, dict):
                            skills_used[str(params.get("skill", "?"))] += 1

            elif entry.get("type") == "user":
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tid = str(block.get("tool_use_id", ""))
                        tool_result_chars[tid] += content_len(block.get("content"))

    usage = {k: 0 for k in WEIGHTS}
    for u in usage_by_request.values():
        for k in usage:
            usage[k] += u[k]

    result_tokens: Counter[str] = Counter()
    for tid, name in tool_calls.items():
        result_tokens[name] += tool_result_chars.get(tid, 0) // CHARS_PER_TOKEN

    cached = usage["cache_read"]
    fresh = usage["input"] + usage["cache_creation"]
    return {
        "session_id": session_id,
        "requests": len(usage_by_request),
        "usage": usage,
        "weighted_tokens": round(sum(usage[k] * w for k, w in WEIGHTS.items())),
        "raw_tokens": sum(usage.values()),
        "cache_hit_rate": round(cached / (cached + fresh), 3) if (cached + fresh) else 0.0,
        "tool_calls": dict(calls_per_tool.most_common()),
        "tool_result_tokens": dict(result_tokens.most_common()),
        "skills_used": dict(skills_used.most_common()),
        "subagent_output_tokens": sidechain_output,
        "first_timestamp": min(stamps) if stamps else None,
        "last_timestamp": max(stamps) if stamps else None,
    }


def write_record(out: Path, rec: dict[str, Any]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = record_path(out, rec["task"], rec["variant"], rec["run"])
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def next_run_index(out: Path, task: str, variant: str) -> int:
    n = 1
    while record_path(out, task, variant, n).exists():
        n += 1
    return n


# ---------------------------------------------------------------------- Ausfuehrung


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


# ------------------------------------------------------------------------ Vergleich


def load_records(out: Path, task: str | None) -> list[dict[str, Any]]:
    if not out.is_dir():
        return []
    recs = []
    for p in sorted(out.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if task and rec.get("task") != task:
            continue
        recs.append(rec)
    return recs


def summarize(recs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Fasst die Laeufe je (Task, Variante) zusammen."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in recs:
        groups.setdefault((r.get("task", "?"), r.get("variant", "?")), []).append(r)

    summary: dict[str, dict[str, Any]] = {}
    for (task, variant), runs in groups.items():
        weighted = [r["weighted_tokens"] for r in runs if r.get("weighted_tokens") is not None]
        costs = [r["cost_usd"] for r in runs if r.get("cost_usd") is not None]
        turns = [r["num_turns"] for r in runs if r.get("num_turns") is not None]
        outcomes = Counter(r.get("outcome", "unset") for r in runs)
        summary[f"{task}::{variant}"] = {
            "task": task,
            "variant": variant,
            "n": len(runs),
            "weighted_median": round(statistics.median(weighted)) if weighted else None,
            "weighted_min": min(weighted) if weighted else None,
            "weighted_max": max(weighted) if weighted else None,
            "cost_median": round(statistics.median(costs), 4) if costs else None,
            "turns_median": round(statistics.median(turns), 1) if turns else None,
            "cache_hit_median": round(statistics.median(
                [r.get("cache_hit_rate", 0.0) for r in runs]), 3),
            "outcomes": dict(outcomes),
        }
    return summary


def verdict(base: dict[str, Any], other: dict[str, Any]) -> str:
    """Urteil nur, wenn die Spannen sich nicht ueberlappen."""
    if not base.get("weighted_median") or not other.get("weighted_median"):
        return "keine Daten"
    if base["n"] < 3 or other["n"] < 3:
        return "zu wenige Laeufe (n < 3)"
    if other["outcomes"].get("fail") or other["outcomes"].get("unset"):
        return "Ertrag offen"
    overlap = not (other["weighted_max"] < base["weighted_min"]
                   or other["weighted_min"] > base["weighted_max"])
    if overlap:
        return "kein belastbarer Unterschied (Spannen ueberlappen)"
    delta = (other["weighted_median"] - base["weighted_median"]) / base["weighted_median"]
    return f"{'guenstiger' if delta < 0 else 'teurer'} um {abs(delta) * 100:.0f} %"


def report(summary: dict[str, dict[str, Any]], baseline: str | None) -> str:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for s in summary.values():
        by_task.setdefault(s["task"], []).append(s)

    out: list[str] = ["# Benchmark"]
    for task, variants in sorted(by_task.items()):
        variants.sort(key=lambda v: v["variant"])
        base_name = baseline if baseline and any(
            v["variant"] == baseline for v in variants) else variants[0]["variant"]
        base = next(v for v in variants if v["variant"] == base_name)

        out += ["", f"## Task: {task}", "", f"Basis: `{base_name}`", "",
                "| Variante | n | Gew. Tokens (Median) | Spanne | Kosten $ | Turns | Cache | Ertrag | Urteil |",
                "|---|---:|---:|---|---:|---:|---:|---|---|"]
        for v in variants:
            span = (f"{v['weighted_min']:,}-{v['weighted_max']:,}".replace(",", ".")
                    if v["weighted_min"] is not None else "-")
            med = f"{v['weighted_median']:,}".replace(",", ".") if v["weighted_median"] else "-"
            ertrag = ", ".join(f"{k}:{n}" for k, n in sorted(v["outcomes"].items()))
            urteil = "Basis" if v["variant"] == base_name else verdict(base, v)
            out.append(
                f"| {v['variant']} | {v['n']} | {med} | {span} | "
                f"{v['cost_median'] if v['cost_median'] is not None else '-'} | "
                f"{v['turns_median'] if v['turns_median'] is not None else '-'} | "
                f"{v['cache_hit_median'] * 100:.0f} % | {ertrag} | {urteil} |")

    out += ["", f"Gewichtung: " + ", ".join(f"{k} x{w}" for k, w in WEIGHTS.items()) + ".",
            "Tool-Result-Tokens sind aus der Zeichenlaenge geschaetzt, die usage-Werte sind exakt."]
    return "\n".join(out)


# ----------------------------------------------------------------------------- CLI


def cmd_run(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    out = Path(args.out)
    prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else args.prompt
    if not prompt:
        print("Weder --prompt noch --prompt-file gesetzt.")
        return 2

    for i in range(args.repeat):
        run = next_run_index(out, args.task, args.variant)
        if args.setup:
            subprocess.run(args.setup, shell=True, cwd=str(project), check=False)
        sid = str(uuid.uuid4())
        print(f"[{i + 1}/{args.repeat}] {args.task}/{args.variant} run {run} session {sid}")
        try:
            meta = execute_run(prompt, project, sid, args.model, args.permission_mode, args.timeout)
        except subprocess.TimeoutExpired:
            print("  Timeout - Lauf wird nicht verbucht.")
            continue
        try:
            measured = measure_session(project, sid)
        except FileNotFoundError as exc:
            print(f"  {exc} - Lauf wird nicht verbucht.")
            continue

        rec = {"task": args.task, "variant": args.variant, "run": run,
               "project": str(project), "prompt_chars": len(prompt),
               "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "outcome": args.outcome, "note": args.note, **meta, **measured}
        p = write_record(out, rec)
        print(f"  gewichtet {rec['weighted_tokens']:,}".replace(",", ".")
              + f" Tokens, {meta['duration_s']} s -> {p}")
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    out = Path(args.out)
    try:
        measured = measure_session(project, args.session_id)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    run = args.run or next_run_index(out, args.task, args.variant)
    rec = {"task": args.task, "variant": args.variant, "run": run, "project": str(project),
           "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "outcome": args.outcome, "note": args.note, "cost_usd": None, "num_turns": None,
           "duration_s": None, **measured}
    print(f"verbucht: {write_record(out, rec)}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    p = record_path(Path(args.out), args.task, args.variant, args.run)
    if not p.is_file():
        print(f"Kein Lauf unter {p}")
        return 1
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["outcome"] = args.outcome
    if args.note:
        rec["note"] = args.note
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{p.name}: outcome={args.outcome}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    recs = load_records(Path(args.out), args.task)
    if not recs:
        print(f"Keine Laufdaten unter {args.out}.")
        return 1
    summary = summarize(recs)
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json
          else report(summary, args.baseline))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(default_out()), help="Ablage der Laufdaten")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--task", required=True, help="Kennung der Testaufgabe")
        p.add_argument("--variant", required=True, help="Kennung der Variante")
        p.add_argument("--project", default=os.getcwd(), help="Arbeitsverzeichnis des Laufs")
        p.add_argument("--outcome", choices=OUTCOMES, default="unset", help="Ertrag des Laufs")
        p.add_argument("--note", default="", help="Freitext zum Lauf")

    r = sub.add_parser("run", help="Laeufe headless ausfuehren und verbuchen")
    common(r)
    r.add_argument("--prompt", help="Testaufgabe als Text")
    r.add_argument("--prompt-file", help="Testaufgabe aus Datei (identisch fuer alle Varianten)")
    r.add_argument("--repeat", type=int, default=3, help="Anzahl Laeufe (Default 3)")
    r.add_argument("--setup", help="Shell-Kommando vor jedem Lauf, z. B. Variante einspielen")
    r.add_argument("--model", help="Modell fuer den Lauf")
    r.add_argument("--permission-mode", default="acceptEdits")
    r.add_argument("--timeout", type=int, default=900, help="Sekunden pro Lauf")
    r.set_defaults(func=cmd_run)

    m = sub.add_parser("measure", help="bereits gelaufene Session verbuchen")
    common(m)
    m.add_argument("--session-id", required=True)
    m.add_argument("--run", type=int, help="Laufnummer (Default: naechste freie)")
    m.set_defaults(func=cmd_measure)

    j = sub.add_parser("judge", help="Ertrag eines verbuchten Laufs setzen")
    j.add_argument("--task", required=True)
    j.add_argument("--variant", required=True)
    j.add_argument("--run", type=int, required=True)
    j.add_argument("--outcome", choices=OUTCOMES, required=True)
    j.add_argument("--note", default="")
    j.set_defaults(func=cmd_judge)

    c = sub.add_parser("compare", help="Varianten gegenueberstellen")
    c.add_argument("--task", help="nur diese Testaufgabe")
    c.add_argument("--baseline", help="Variante, gegen die verglichen wird")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_compare)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
