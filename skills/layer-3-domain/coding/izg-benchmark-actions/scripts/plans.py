#!/usr/bin/env python3
"""Messplaene - die Definition einer Messung, festgehalten damit sie wiederholbar bleibt.

Der Sinn: eine Optimierung zeigt ihren Wert erst, wenn man Monate spaeter *dieselbe*
Messung noch einmal fahren kann. Testaufgabe, Projekt, Modell und die Umschaltkommandos
der Varianten leben sonst nur in der Shell-History - und eine aus dem Gedaechtnis
rekonstruierte Messung misst etwas anderes, ohne dass es auffaellt.

Ein Plan liegt unter <out>/plans/<task>.json, also neben den Laufdaten, die er erzeugt.
Er ist bewusst duenn: er ersetzt keine Option, er fuellt nur die, die beim Aufruf fehlen.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import runs

# Felder, die run() aus einem Plan uebernehmen kann. Der Variantenteil steht getrennt,
# weil er pro Variante verschieden ist.
PLAN_OPTIONS = ("prompt_file", "project", "model", "permission_mode", "timeout")


def plans_dir(out: Path) -> Path:
    return out / "plans"


def plan_path(out: Path, task: str) -> Path:
    return plans_dir(out) / f"{runs.safe_name(task)}.json"


def prompt_sha(text: str) -> str:
    """Pruefsumme der Testaufgabe. Kurz gehalten - sie soll Abweichung anzeigen, nicht signieren."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load_plan(out: Path, task: str) -> dict[str, Any] | None:
    p = plan_path(out, task)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def new_plan(task: str) -> dict[str, Any]:
    return {
        "task": task,
        **{k: None for k in PLAN_OPTIONS},
        "prompt_sha": None,
        "baseline": None,
        "variants": {},
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_at": None,
    }


def save_plan(out: Path, plan: dict[str, Any]) -> Path:
    plan["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p = plan_path(out, plan["task"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def list_plans(out: Path) -> list[dict[str, Any]]:
    d = plans_dir(out)
    if not d.is_dir():
        return []
    out_list = []
    for p in sorted(d.glob("*.json")):
        try:
            out_list.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out_list


def fill_from_plan(plan: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fuellt nur, was nicht gesetzt ist - die Kommandozeile schlaegt den Plan immer.

    Gibt die ergaenzten Werte und Hinweiszeilen zurueck. Ein Wert, der auf der
    Kommandozeile *anders* steht als im Plan, wird nicht stillschweigend uebernommen,
    sondern gemeldet: das ist der Moment, in dem eine Wiederholungsmessung von ihrer
    Vorlage abweicht, und genau der darf nicht unbemerkt passieren.
    """
    filled = dict(values)
    notes: list[str] = []
    for key in PLAN_OPTIONS:
        planned = plan.get(key)
        if planned is None:
            continue
        if filled.get(key) is None:
            filled[key] = planned
        elif filled[key] != planned:
            notes.append(f"{key}: Aufruf '{filled[key]}' weicht vom Messplan '{planned}' ab")
    return filled, notes


def variant_setup(plan: dict[str, Any], variant: str) -> str | None:
    return (plan.get("variants") or {}).get(variant, {}).get("setup")


def record_baseline(plan: dict[str, Any], baseline: str | None) -> str | None:
    """Haelt die Basis der Testaufgabe im Plan fest. Gibt eine Hinweiszeile zurueck.

    Die Basis gehoert zur Messdefinition, nicht an den einzelnen Aufruf: wer sie vergisst,
    bekommt sonst klaglos die alphabetisch erste Variante als Bezugspunkt und damit ein
    Urteil ueber eine Frage, die er nicht gestellt hat.
    """
    if baseline is None:
        return None
    known = plan.get("baseline")
    plan["baseline"] = baseline
    if known is None:
        return f"Messplan ergaenzt: Basis '{baseline}'"
    if known != baseline:
        return f"Messplan aktualisiert: Basis '{known}' -> '{baseline}'"
    return None


def resolve_baselines(out: Path, tasks: Iterable[str],
                      cli_baseline: str | None) -> tuple[dict[str, str | None], list[str]]:
    """Basis je Testaufgabe: Kommandozeile schlaegt Messplan, Messplan schlaegt Alphabet.

    Ohne diesen Griff in den Plan haengt der Bezugspunkt eines Urteils daran, ob jemand
    beim Aufruf `--baseline` getippt hat - und die Fehlmessung faellt niemandem auf, weil
    die Tabelle mit einer anderen Basis genauso plausibel aussieht. Eine auf der
    Kommandozeile genannte Basis wandert dabei gleich in den bestehenden Messplan -
    einmal genannt, danach nicht mehr noetig. Plaene, die es noch nicht gibt, werden
    dafuer nicht angelegt: der Plan entsteht beim Messen, nicht beim Auswerten.
    """
    resolved: dict[str, str | None] = {}
    notes: list[str] = []
    for task in sorted(set(tasks)):
        plan = load_plan(out, task)
        if cli_baseline:
            resolved[task] = cli_baseline
            if plan is not None and (note := record_baseline(plan, cli_baseline)):
                save_plan(out, plan)
                notes.append(f"  {note}")
            continue
        planned = (plan or {}).get("baseline")
        resolved[task] = planned
        if not planned:
            notes.append(f"! {task}: keine Basis angegeben und keine im Messplan - es wird "
                         f"die alphabetisch erste Variante verglichen. Mit --baseline "
                         f"festlegen, dann steht sie im Plan.")
    return resolved, notes


def record_variant(plan: dict[str, Any], variant: str, setup: str | None) -> str | None:
    """Haelt die Umschaltung einer Variante im Plan fest. Gibt eine Hinweiszeile zurueck.

    Neu gemessene Varianten wandern automatisch in den Plan - sonst wuerde er genau bei
    der Variante luecken haben, die man beim naechsten Mal wieder braucht.
    """
    variants = plan.setdefault("variants", {})
    known = variants.get(variant, {}).get("setup")
    if variant not in variants:
        variants[variant] = {"setup": setup}
        return f"Messplan ergaenzt: Variante '{variant}'"
    if setup is not None and known != setup:
        variants[variant]["setup"] = setup
        return f"Messplan aktualisiert: Umschaltung von '{variant}' geaendert"
    return None
