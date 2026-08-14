#!/usr/bin/env python3
"""Baut, schreibt und laedt Laufdatensaetze - das Modul, dem der Laufdatensatz gehoert.

Ein Lauf entsteht auf zwei Wegen (per `run` frisch ausgefuehrt, per `measure` nachtraeglich
verbucht), landet aber spaeter gleichberechtigt in derselben Vergleichstabelle. Damit beide
Wege denselben Feldsatz erzeugen, geht keiner an build_record() vorbei - fehlende Werte sind
ausdruecklich None, nicht abwesend. Dateinamensschema und Laufnummern-Vergabe leben im
selben Modul, weil sie an dasselbe Ablageverzeichnis gebunden sind wie der Datensatz selbst.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Felder, die build_record() garantiert belegt - Basis fuer summarize()'s Zugriff ohne .get().
RECORD_FIELDS = (
    "task", "variant", "run", "project", "recorded_at", "outcome", "note",
    "prompt_chars", "duration_s", "exit_code", "cost_usd", "num_turns",
    "cli_subtype", "stderr_tail",
    "session_id", "requests", "usage", "weighted_tokens", "raw_tokens",
    "cache_hit_rate", "tool_calls", "tool_result_tokens", "skills_used",
    "subagent_output_tokens", "first_timestamp", "last_timestamp",
    # Vergleichbarkeit ueber die Zeit: was den Preis eines Laufs verschiebt, ohne dass die
    # gemessene Variante sich geaendert hat. Ohne diese Felder kann kein spaeterer Vergleich
    # erkennen, dass er Aepfel gegen Birnen stellt.
    "round", "model", "cli_version", "prompt_sha",
)

# Felder aus execute_run() - nur bei per `run` erzeugten Laeufen vorhanden.
_EXEC_FIELDS = ("duration_s", "exit_code", "cost_usd", "num_turns", "cli_subtype", "stderr_tail")

# Umgebungsfelder - bei `measure` nachgetragene Laeufe kennen sie oft nicht.
_ENV_FIELDS = ("round", "model", "cli_version", "prompt_sha")


def safe_name(s: str) -> str:
    """Kennungen -> Dateinamensbestandteil. Auch von plans.py genutzt, damit ein Messplan
    unter demselben Namen liegt wie die Laufdaten, die er erzeugt."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", s)


def record_path(out: Path, task: str, variant: str, run: int) -> Path:
    return out / f"{safe_name(task)}__{safe_name(variant)}__{run:02d}.json"


def next_run_index(out: Path, task: str, variant: str) -> int:
    n = 1
    while record_path(out, task, variant, n).exists():
        n += 1
    return n


def build_record(*, task: str, variant: str, run: int, project: Path, outcome: str, note: str,
                  measured: dict[str, Any], meta: dict[str, Any] | None = None,
                  prompt_chars: int | None = None,
                  env: dict[str, Any] | None = None) -> dict[str, Any]:
    """Der einzige Konstruktor fuer einen Laufdatensatz - cmd_run und cmd_measure gehen beide hindurch.

    `meta` (die Rueckgabe von execute_run) liegt nur bei per `run` erzeugten Laeufen vor.
    Fehlt es, werden seine Felder ausdruecklich auf None gesetzt statt zu fehlen - so bekommt
    ein per `measure` nachgetragener Lauf denselben Feldsatz wie ein per `run` erzeugter.
    `env` traegt Messrunde, Modell, CLI-Version und Aufgaben-Pruefsumme; fehlende Werte sind
    dort ebenfalls None, damit ein spaeterer Vergleich "unbekannt" von "abweichend" trennen kann.
    """
    exec_meta = {f: (meta.get(f) if meta else None) for f in _EXEC_FIELDS}
    env_meta = {f: (env.get(f) if env else None) for f in _ENV_FIELDS}
    rec = {
        "task": task, "variant": variant, "run": run, "project": str(project),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outcome": outcome, "note": note, "prompt_chars": prompt_chars,
        **exec_meta, **env_meta, **measured,
    }
    assert set(rec) == set(RECORD_FIELDS), f"build_record: Feldsatz weicht ab: {set(rec) ^ set(RECORD_FIELDS)}"
    return rec


def write_record(out: Path, rec: dict[str, Any]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = record_path(out, rec["task"], rec["variant"], rec["run"])
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


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
        # Laufdaten aus einer aelteren Fassung kennen die Umgebungsfelder nicht. Sie fehlen
        # lassen hiesse, dass der Vergleich sie fuer "abweichend" statt "unbekannt" haelt.
        for f in _ENV_FIELDS:
            rec.setdefault(f, None)
        recs.append(rec)
    return recs
