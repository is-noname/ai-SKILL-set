#!/usr/bin/env python3
"""Baut, schreibt und laedt Laufdatensaetze - das Modul, dem der Laufdatensatz gehoert.

Ein Lauf entsteht auf zwei Wegen (per `run` frisch ausgefuehrt, per `measure` nachtraeglich
verbucht), landet aber spaeter gleichberechtigt in derselben Vergleichstabelle. Damit beide
Wege denselben Feldsatz erzeugen, geht keiner an build_record() vorbei - fehlende Werte sind
ausdruecklich None, nicht abwesend. Dateinamensschema und Laufnummern-Vergabe leben im
selben Modul, weil sie an dasselbe Ablageverzeichnis gebunden sind wie der Datensatz selbst.

Die Laufdaten liegen als append-only `runs.jsonl` je Ausgabeverzeichnis: ein Lauf ist eine
angehaengte Zeile, nie eine Neuserialisierung der Gesamtdatei. Bereits gemessene Laeufe aus
der frueheren Fassung (eine `.json`-Datei je Lauf) werden beim Lesen weiter mitgenommen -
eine Messreihe soll durch einen Formatwechsel nicht entwertet werden.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Gewichte in Input-Token-Aequivalenten, angelehnt an die Anthropic-Preisstruktur.
# Ein Lauf, der den Cache schont, sieht in rohen Summen sonst schlechter aus als er ist.
# Sie stehen hier, weil `weighted_tokens` ein Feld des Laufdatensatzes ist: wer die Gewichte
# aendert, aendert die Bedeutung aller frueher geschriebenen Datensaetze - dann neu messen.
WEIGHTS = {"input": 1.0, "cache_creation": 1.25, "cache_read": 0.1, "output": 5.0}

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


RUNS_FILE = "runs.jsonl"


def runs_path(out: Path) -> Path:
    return out / RUNS_FILE


def legacy_record_path(out: Path, task: str, variant: str, run: int) -> Path:
    """Ablage der frueheren Fassung: eine Datei je Lauf. Wird nicht mehr geschrieben, aber
    weiter gelesen und - beim Nachurteilen - an Ort und Stelle geaendert."""
    return out / f"{safe_name(task)}__{safe_name(variant)}__{run:02d}.json"


def next_run_index(out: Path, task: str, variant: str) -> int:
    """Kleinste freie Laufnummer der Variante - Luecken werden aufgefuellt.

    Fragt die geladenen Datensaetze, nicht das Dateisystem: eine Laufnummer kann in
    `runs.jsonl` stehen oder in einer Altdatei, beides belegt sie gleichermassen.
    """
    belegt = {r["run"] for r in load_records(out, task)
              if r.get("variant") == variant and isinstance(r.get("run"), int)}
    n = 1
    while n in belegt:
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
    """Haengt den Datensatz als eine Zeile an `runs.jsonl` an."""
    out.mkdir(parents=True, exist_ok=True)
    p = runs_path(out)
    # Eine abgeschnittene letzte Zeile (abgebrochener Schreibvorgang) wuerde sonst mit der
    # neuen verschmelzen und beide unlesbar machen - lieber eine leere Zeile dazwischen.
    trenner = "\n" if p.is_file() and not p.read_text(encoding="utf-8").endswith("\n") else ""
    with p.open("a", encoding="utf-8") as fh:
        fh.write(trenner + json.dumps(rec, ensure_ascii=False) + "\n")
    return p


def _prepare(rec: Any, task: str | None) -> dict[str, Any] | None:
    """Filtert nach Testaufgabe und ergaenzt fehlende Umgebungsfelder. None = nicht uebernehmen."""
    if not isinstance(rec, dict):
        return None
    if task and rec.get("task") != task:
        return None
    # Laufdaten aus einer aelteren Fassung kennen die Umgebungsfelder nicht. Sie fehlen
    # lassen hiesse, dass der Vergleich sie fuer "abweichend" statt "unbekannt" haelt.
    for f in _ENV_FIELDS:
        rec.setdefault(f, None)
    return rec


def _load_jsonl(p: Path, task: str | None) -> list[dict[str, Any]]:
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    recs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # defekte/abgeschnittene Zeile: ueberspringen, nicht abbrechen
        if (rec := _prepare(rec, task)) is not None:
            recs.append(rec)
    return recs


def _load_legacy(out: Path, task: str | None) -> list[dict[str, Any]]:
    recs = []
    for p in sorted(out.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if (rec := _prepare(rec, task)) is not None:
            recs.append(rec)
    return recs


def load_records(out: Path, task: str | None) -> list[dict[str, Any]]:
    """Alle Laufdaten des Verzeichnisses - erst die Altdateien, dann `runs.jsonl`."""
    if not out.is_dir():
        return []
    return _load_legacy(out, task) + _load_jsonl(runs_path(out), task)


def update_record(out: Path, task: str, variant: str, run: int,
                  changes: dict[str, Any]) -> bool:
    """Aendert einen bereits verbuchten Lauf (Nachurteil) - der einzige Schreibweg, der
    nicht anhaengt. Liegt der Lauf noch als Altdatei vor, wird sie geaendert; sonst wird
    `runs.jsonl` einmal neu geschrieben. Rueckgabe: ob der Lauf gefunden wurde."""
    alt = legacy_record_path(out, task, variant, run)
    if alt.is_file():
        try:
            rec = json.loads(alt.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        rec.update(changes)
        alt.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    p = runs_path(out)
    if not p.is_file():
        return False
    zeilen, getroffen = [], False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                zeilen.append(line)  # defekte Zeile unangetastet weiterreichen
                continue
            if (rec.get("task"), rec.get("variant"), rec.get("run")) == (task, variant, run):
                rec.update(changes)
                getroffen = True
                line = json.dumps(rec, ensure_ascii=False)
            zeilen.append(line)
    if not getroffen:
        return False
    tmp = p.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    tmp.replace(p)
    return True
