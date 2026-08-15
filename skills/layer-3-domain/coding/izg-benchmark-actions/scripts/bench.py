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
    bench.py history --task t1        # Verlauf ueber mehrere Messrunden
    bench.py plan show --task t1      # gespeicherte Messdefinition

Alle Laufdaten liegen als JSON unter --out (Default: ~/.local/share/izg-bench).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import messlauf
import plans
import runs
import transcript

# Gewichte in Input-Token-Aequivalenten, angelehnt an die Anthropic-Preisstruktur.
# Ein Lauf, der den Cache schont, sieht in rohen Summen sonst schlechter aus als er ist.
WEIGHTS = {"input": 1.0, "cache_creation": 1.25, "cache_read": 0.1, "output": 5.0}

OUTCOMES = ("ok", "partial", "fail", "unset")


# --------------------------------------------------------------------------- Pfade


def default_out() -> Path:
    """Dauerhafte Ablage, nicht /tmp.

    Wer messen will, ob eine Optimierung etwas gebracht hat, braucht die Messung von vor
    drei Monaten noch. In /tmp ist sie nach dem naechsten Neustart weg, und dann bleibt
    nur der Vergleich gegen eine Erinnerung.
    """
    if env := os.environ.get("IZG_BENCH_OUT"):
        return Path(env).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "izg-bench"


def cli_version() -> str | None:
    """Version der Claude-CLI - ein stiller Preistreiber zwischen zwei Messrunden."""
    try:
        proc = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


# ----------------------------------------------------------------------- Messung


def measure_session(project: Path, session_id: str) -> dict[str, Any]:
    """Liest ein einzelnes Transcript und verbucht seinen Verbrauch ueber WEIGHTS."""
    path = transcript.transcript_path(project, session_id)
    su = transcript.read_session(path, session_id)

    cached = su.usage["cache_read"]
    fresh = su.usage["input"] + su.usage["cache_creation"]
    return {
        "session_id": su.session_id,
        "requests": su.requests,
        "usage": su.usage,
        "weighted_tokens": round(sum(su.usage[k] * w for k, w in WEIGHTS.items())),
        "raw_tokens": sum(su.usage.values()),
        "cache_hit_rate": round(cached / (cached + fresh), 3) if (cached + fresh) else 0.0,
        "tool_calls": su.tool_calls,
        "tool_result_tokens": su.tool_result_tokens,
        "skills_used": su.skills_used,
        "subagent_output_tokens": su.subagent_output_tokens,
        "first_timestamp": su.first_timestamp,
        "last_timestamp": su.last_timestamp,
    }


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


class ClaudeAusfuehrung:
    """Der Adapter auf die echte Welt - der einzige Teil des Messlaufs, der Geld kostet.

    Haelt zusammen, was `messlauf.fahre()` bewusst nicht kennt: Shell, `claude -p` und
    das Transcript auf der Platte. Der Test setzt an derselben Stelle einen Fake ein.
    """

    def schalte_um(self, setup: str, project: Path) -> None:
        subprocess.run(setup, shell=True, cwd=str(project), check=False)

    def starte(self, auftrag: messlauf.Laufauftrag, session_id: str) -> dict[str, Any]:
        return execute_run(auftrag.prompt, auftrag.project, session_id, auftrag.model,
                           auftrag.permission_mode, auftrag.timeout)

    def miss(self, project: Path, session_id: str) -> dict[str, Any]:
        return measure_session(project, session_id)


# ------------------------------------------------------------------------ Vergleich


def _distinct(group: list[dict[str, Any]], field: str) -> list[str]:
    """Die belegten Werte eines Umgebungsfelds. Unbekannt (None) zaehlt nicht als Abweichung."""
    return sorted({r[field] for r in group if r.get(field)})


def summarize(recs: list[dict[str, Any]],
              group_round: bool = False) -> dict[str, dict[str, Any]]:
    """Fasst die Laeufe je (Task, Variante) zusammen - bei group_round zusaetzlich je Messrunde.

    task/variant sind laut Schema (runs.build_record) in jedem Datensatz gesetzt - hier direkt
    indiziert. Die uebrigen Felder bleiben ueber .get()/is-not-None defensiv, weil Altdaten aus
    frueheren Laeufen im Ablageverzeichnis liegen koennen, die vor diesem Schema entstanden sind.

    Modell, CLI-Version, Messrunde und Aufgaben-Pruefsumme werden als Mengen mitgefuehrt, nicht
    als Einzelwerte: eine Variante, die aus zwei Modellen zusammengesetzt ist, hat kein Modell -
    sie hat ein Problem, und verdict() muss das sehen koennen.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for r in recs:
        rnd = (r.get("round") or "ohne-runde") if group_round else ""
        groups.setdefault((r["task"], rnd, r["variant"]), []).append(r)

    summary: dict[str, dict[str, Any]] = {}
    for (task, rnd, variant), group in groups.items():
        weighted = [r["weighted_tokens"] for r in group if r.get("weighted_tokens") is not None]
        costs = [r["cost_usd"] for r in group if r.get("cost_usd") is not None]
        turns = [r["num_turns"] for r in group if r.get("num_turns") is not None]
        outcomes = Counter(r.get("outcome", "unset") for r in group)
        key = f"{task}::{rnd}::{variant}" if group_round else f"{task}::{variant}"
        summary[key] = {
            "task": task,
            "variant": variant,
            "round": rnd or None,
            "n": len(group),
            "weighted_median": round(statistics.median(weighted)) if weighted else None,
            "weighted_min": min(weighted) if weighted else None,
            "weighted_max": max(weighted) if weighted else None,
            "cost_median": round(statistics.median(costs), 4) if costs else None,
            "turns_median": round(statistics.median(turns), 1) if turns else None,
            "cache_hit_median": round(statistics.median(
                [r.get("cache_hit_rate", 0.0) for r in group]), 3),
            "outcomes": dict(outcomes),
            "models": _distinct(group, "model"),
            "rounds": _distinct(group, "round"),
            "cli_versions": _distinct(group, "cli_version"),
            "prompt_shas": _distinct(group, "prompt_sha"),
            "last_recorded": max((r.get("recorded_at") or "" for r in group), default="") or None,
        }
    return summary


def comparability(base: dict[str, Any], other: dict[str, Any],
                  strict_round: bool = True) -> dict[str, Any] | None:
    """Prueft, ob die beiden Seiten ueberhaupt gegeneinander stehen duerfen.

    Alle drei Faelle verschieben die Kosten, ohne dass die gemessene Variante sich geaendert
    hat - ein Prozentwert waere dann eine Aussage ueber das Modell oder ueber eine andere
    Aufgabe, nicht ueber die Optimierung. Darum kein Urteil statt eines vorsichtigen Urteils.
    """
    shas = set(base.get("prompt_shas") or []) | set(other.get("prompt_shas") or [])
    if len(shas) > 1:
        return {"art": "aufgabe-geaendert", "shas": sorted(shas)}
    modelle = set(base.get("models") or []) | set(other.get("models") or [])
    if len(modelle) > 1:
        return {"art": "modell-gemischt", "modelle": sorted(modelle)}
    if strict_round:
        runden = set(base.get("rounds") or []) | set(other.get("rounds") or [])
        if len(runden) > 1:
            return {"art": "runden-gemischt", "runden": sorted(runden)}
    return None


def verdict(base: dict[str, Any], other: dict[str, Any],
            strict_round: bool = True) -> dict[str, Any]:
    """Urteil als strukturierter Wert: Art, Delta und die Belegzahlen, auf denen er ruht.

    Die Zurueckhaltung der Regeln (n >= 3, kein Urteil bei offenem Ertrag, kein
    Ausweichen auf Mediane bei ueberlappenden Spannen) bleibt unveraendert - nur die
    Darstellung wird strukturiert statt eines deutschen Satzes.

    Vorgeschaltet ist die Vergleichbarkeit: verschiedene Modelle, eine geaenderte
    Testaufgabe oder Zahlen aus zwei Messrunden erzeugen kein Urteil, sondern eine
    Aufforderung, neu zu messen.
    """
    if base["task"] == other["task"] and base["variant"] == other["variant"]:
        return {"art": "basis"}
    if base.get("weighted_median") is None or other.get("weighted_median") is None:
        return {"art": "keine-daten"}
    if blocker := comparability(base, other, strict_round):
        return blocker
    if other["outcomes"].get("fail") or other["outcomes"].get("unset"):
        return {"art": "ertrag-offen", "outcomes": dict(other["outcomes"])}
    # n < 3 sperrt das Urteil nicht mehr, es kennzeichnet es. Bei einem Lauf ist die
    # Spanne ein Punkt - Spannen koennen dann nicht ueberlappen, also faellt das Urteil
    # immer, auch wenn der Unterschied reine Streuung ist. Deshalb "duenn".
    duenn = base["n"] < 3 or other["n"] < 3
    beleg = {"duenn": duenn, "n_basis": base["n"], "n_variante": other["n"]}
    overlap = not (other["weighted_max"] < base["weighted_min"]
                   or other["weighted_min"] > base["weighted_max"])
    if overlap:
        return {"art": "kein-unterschied", **beleg,
                "basis_spanne": [base["weighted_min"], base["weighted_max"]],
                "variante_spanne": [other["weighted_min"], other["weighted_max"]]}
    if base["weighted_median"] == 0:
        # Basis-Median 0: eine Prozentangabe waere eine Division durch 0.
        return {"art": "teurer", "delta": None, **beleg,
                "basis_median": 0, "variante_median": other["weighted_median"]}
    delta = (other["weighted_median"] - base["weighted_median"]) / base["weighted_median"]
    return {"art": "guenstiger" if delta < 0 else "teurer", "delta": round(delta, 4), **beleg,
            "basis_median": base["weighted_median"], "variante_median": other["weighted_median"]}


def render_verdict(v: dict[str, Any]) -> str:
    """Rendert einen Urteilswert als deutschen Satz - Wortlaut zeichengleich zur Vorversion."""
    art = v["art"]
    if art == "basis":
        return "Basis"
    if art == "keine-daten":
        return "keine Daten"
    if art == "aufgabe-geaendert":
        return "Testaufgabe geaendert - nicht vergleichbar"
    if art == "modell-gemischt":
        return "verschiedene Modelle (" + ", ".join(v["modelle"]) + ") - nicht vergleichbar"
    if art == "runden-gemischt":
        return "verschiedene Messrunden - Basis neu messen"
    if art == "ertrag-offen":
        return "Ertrag offen"
    zusatz = f", n={v['n_variante']} - ungesichert" if v.get("duenn") else ""
    if art == "kein-unterschied":
        return f"kein belastbarer Unterschied (Spannen ueberlappen{zusatz})"
    if v["delta"] is None:
        return f"{art} (Basis-Median 0{zusatz})"
    return f"{art} um {abs(v['delta']) * 100:.0f} %" + (f" ({zusatz.lstrip(', ')})" if zusatz else "")


def base_for(task: str, baseline: "str | Mapping[str, str | None] | None") -> str | None:
    """Die Basis fuer eine Testaufgabe - entweder eine fuer alle oder eine je Task."""
    if isinstance(baseline, Mapping):
        return baseline.get(task)
    return baseline


def select_base(variants: list[dict[str, Any]],
                baseline: "str | Mapping[str, str | None] | None") -> str:
    variants = sorted(variants, key=lambda v: v["variant"])
    wanted = base_for(variants[0]["task"], baseline)
    if wanted and any(v["variant"] == wanted for v in variants):
        return wanted
    return variants[0]["variant"]


def resolve_baselines(out: Path, summary: dict[str, dict[str, Any]],
                      cli_baseline: str | None) -> tuple[dict[str, str | None], list[str]]:
    """Basis je Testaufgabe: Kommandozeile schlaegt Messplan, Messplan schlaegt Alphabet.

    Ohne diesen Griff in den Plan haengt der Bezugspunkt eines Urteils daran, ob jemand
    beim Aufruf `--baseline` getippt hat - und die Fehlmessung faellt niemandem auf, weil
    die Tabelle mit einer anderen Basis genauso plausibel aussieht.
    """
    resolved: dict[str, str | None] = {}
    notes: list[str] = []
    for task in sorted({s["task"] for s in summary.values()}):
        if cli_baseline:
            resolved[task] = cli_baseline
            continue
        planned = (plans.load_plan(out, task) or {}).get("baseline")
        resolved[task] = planned
        if not planned:
            notes.append(f"! {task}: keine Basis angegeben und keine im Messplan - es wird "
                         f"die alphabetisch erste Variante verglichen. Mit --baseline "
                         f"festlegen, dann steht sie im Plan.")
    return resolved, notes


def persist_baseline(out: Path, baselines: dict[str, str | None],
                     cli_baseline: str | None) -> None:
    """Eine auf der Kommandozeile genannte Basis wandert in den Messplan.

    Analog zur Umschaltung einer Variante: einmal genannt, danach nicht mehr noetig.
    Plaene, die es noch nicht gibt, werden dafuer nicht angelegt - der Plan entsteht
    beim Messen, nicht beim Auswerten.
    """
    if not cli_baseline:
        return
    for task in baselines:
        plan = plans.load_plan(out, task)
        if plan is None:
            continue
        if note := plans.record_baseline(plan, cli_baseline):
            plans.save_plan(out, plan)
            print(f"  {note}")


def attach_verdicts(summary: dict[str, dict[str, Any]],
                    baseline: "str | Mapping[str, str | None] | None",
                    strict_round: bool = True) -> None:
    """Haengt an jede Variante ihr Urteil gegen die Basis derselben Testaufgabe und Messrunde an.

    Die Messrunde gehoert in den Gruppenschluessel: innerhalb einer Runde vergleicht man
    Varianten, ueber Runden hinweg vergleicht man Zeitpunkte - das sind zwei Fragen, und
    ein gemeinsamer Basiswert wuerde sie vermengen.
    """
    by_group: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    for s in summary.values():
        by_group.setdefault((s["task"], s.get("round")), []).append(s)
    for variants in by_group.values():
        base_name = select_base(variants, baseline)
        base = next(v for v in variants if v["variant"] == base_name)
        for v in variants:
            v["urteil"] = verdict(base, v, strict_round)


def report(summary: dict[str, dict[str, Any]],
           baseline: "str | Mapping[str, str | None] | None",
           show_round: bool = False) -> str:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for s in summary.values():
        by_task.setdefault(s["task"], []).append(s)

    out: list[str] = ["# Benchmark"]
    for task, variants in sorted(by_task.items()):
        variants.sort(key=lambda v: ((v.get("round") or ""), v["variant"]))
        base_name = select_base(variants, baseline)

        head = "| Runde " if show_round else ""
        sep = "|---" if show_round else ""
        out += ["", f"## Task: {task}", "", f"Basis: `{base_name}`", "",
                head + "| Variante | n | Gew. Tokens (Median) | Spanne | Kosten $ | Turns | Cache | Ertrag | Urteil |",
                sep + "|---|---:|---:|---|---:|---:|---:|---|---|"]
        for v in variants:
            span = (f"{v['weighted_min']:,}-{v['weighted_max']:,}".replace(",", ".")
                    if v["weighted_min"] is not None else "-")
            med = (f"{v['weighted_median']:,}".replace(",", ".")
                   if v["weighted_median"] is not None else "-")
            ertrag = ", ".join(f"{k}:{n}" for k, n in sorted(v["outcomes"].items()))
            urteil = render_verdict(v["urteil"])
            prefix = f"| {v.get('round') or '-'} " if show_round else ""
            out.append(
                prefix + f"| {v['variant']} | {v['n']} | {med} | {span} | "
                f"{v['cost_median'] if v['cost_median'] is not None else '-'} | "
                f"{v['turns_median'] if v['turns_median'] is not None else '-'} | "
                f"{v['cache_hit_median'] * 100:.0f} % | {ertrag} | {urteil} |")

    out += ["", f"Gewichtung: " + ", ".join(f"{k} x{w}" for k, w in WEIGHTS.items()) + ".",
            "Tool-Result-Tokens sind aus der Zeichenlaenge geschaetzt, die usage-Werte sind exakt."]
    return "\n".join(out)


# --------------------------------------------------------------------------- Verlauf


def trend(summary: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Wie sich eine Variante ueber die Messrunden bewegt hat - je Task und Variante.

    Bewusst getrennt vom Urteil: die Runden liegen Wochen auseinander, dazwischen liegen
    Modellwechsel und CLI-Versionen. Was hier steht, ist eine Beobachtung mit Datum, kein
    Beleg. Belastbar wird eine Optimierung erst, wenn die alte Fassung in derselben Runde
    noch einmal mitgemessen wurde.
    """
    by_variant: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for s in summary.values():
        if s.get("round") and s.get("weighted_median") is not None:
            by_variant.setdefault((s["task"], s["variant"]), []).append(s)

    result: dict[str, list[dict[str, Any]]] = {}
    for (task, variant), punkte in by_variant.items():
        if len(punkte) < 2:
            continue
        punkte.sort(key=lambda p: p["round"])
        reihe = []
        for i, p in enumerate(punkte):
            vor = punkte[i - 1] if i else None
            delta = None
            if vor and vor["weighted_median"]:
                delta = round((p["weighted_median"] - vor["weighted_median"])
                              / vor["weighted_median"], 4)
            reihe.append({
                "round": p["round"], "weighted_median": p["weighted_median"],
                "n": p["n"], "delta_zur_vorrunde": delta,
                "models": p["models"], "cli_versions": p["cli_versions"],
                "umgebung_gewechselt": bool(
                    vor and (set(p["models"]) != set(vor["models"])
                             or set(p["cli_versions"]) != set(vor["cli_versions"]))),
            })
        result[f"{task}::{variant}"] = reihe
    return result


def render_trend(trends: dict[str, list[dict[str, Any]]]) -> str:
    if not trends:
        return ("\n## Verlauf\n\nNur eine Messrunde vorhanden - kein Verlauf. "
                "Fuer den Vergleich ueber die Zeit dieselbe Variante in einer zweiten "
                "Runde erneut messen (`--round`).")
    out = ["", "## Verlauf ueber die Messrunden", "",
           "Beobachtung mit Datum, kein Beleg: zwischen den Runden liegt mehr als die "
           "Optimierung. Belastbar ist nur ein Urteil innerhalb einer Runde."]
    for key, reihe in sorted(trends.items()):
        task, variant = key.split("::", 1)
        out += ["", f"**{task} / {variant}**", ""]
        for p in reihe:
            med = f"{p['weighted_median']:,}".replace(",", ".")
            d = (f" ({p['delta_zur_vorrunde'] * 100:+.0f} %)"
                 if p["delta_zur_vorrunde"] is not None else "")
            warn = "  <- Modell/CLI gewechselt" if p["umgebung_gewechselt"] else ""
            out.append(f"- {p['round']}: {med} gew. Tokens (n={p['n']}){d}{warn}")
    return "\n".join(out)


# ----------------------------------------------------------------------------- CLI


def resolve_plan(args: argparse.Namespace, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Traegt Messplan und Kommandozeile zusammen. Der Aufruf schlaegt den Plan immer."""
    plan = None if args.no_plan else plans.load_plan(out, args.task)
    values = {k: getattr(args, k, None) for k in plans.PLAN_OPTIONS}
    if plan:
        print(f"Messplan: {plans.plan_path(out, args.task)}")
        values, notes = plans.fill_from_plan(plan, values)
        for n in notes:
            print(f"  ! {n}")
    else:
        plan = plans.new_plan(args.task)
    return plan, values


def cmd_run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    plan, values = resolve_plan(args, out)

    project = Path(values["project"] or os.getcwd()).resolve()
    permission_mode = values["permission_mode"] or "acceptEdits"
    timeout = values["timeout"] or 900
    prompt_file = Path(values["prompt_file"]).resolve() if values["prompt_file"] else None

    if args.prompt:
        prompt = args.prompt
    elif prompt_file:
        prompt = prompt_file.read_text(encoding="utf-8")
    else:
        print("Weder --prompt noch --prompt-file gesetzt (und kein Messplan hinterlegt).")
        return 2

    sha = plans.prompt_sha(prompt)
    if plan.get("prompt_sha") and plan["prompt_sha"] != sha:
        print(f"  ! Testaufgabe hat sich seit dem Messplan geaendert "
              f"({plan['prompt_sha']} -> {sha}). Frueher gemessene Laeufe sind nicht mehr "
              f"vergleichbar - alle Varianten neu messen.")

    setup = args.setup if args.setup is not None else plans.variant_setup(plan, args.variant)
    if note := plans.record_variant(plan, args.variant, setup):
        print(f"  {note}")
    if setup is None:
        print("  ! Keine Umschaltung (--setup) fuer diese Variante - es wird der Zustand "
              "gemessen, wie er gerade im Projekt liegt.")

    # Der Plan wird vor dem ersten Lauf geschrieben: ein Abbruch mittendrin soll die
    # Messdefinition nicht verlieren, sie ist das Teuerste an der Sache.
    for k in plans.PLAN_OPTIONS:
        if values.get(k) is not None:
            plan[k] = str(prompt_file) if k == "prompt_file" and prompt_file else values[k]
    plan["prompt_sha"] = sha
    plans.save_plan(out, plan)

    messrunde = args.round or date.today().isoformat()
    env = {"round": messrunde, "model": values["model"],
           "cli_version": cli_version(), "prompt_sha": sha}
    print(f"Messrunde {messrunde}, Modell {values['model'] or '(CLI-Default)'}, "
          f"CLI {env['cli_version'] or '?'}")

    auftrag = messlauf.Laufauftrag(
        task=args.task, variant=args.variant, project=project, prompt=prompt,
        outcome=args.outcome, note=args.note, setup=setup, model=values["model"],
        permission_mode=permission_mode, timeout=timeout, env=env)

    def melde(i: int, gesamt: int, run: int, sid: str) -> None:
        print(f"[{i}/{gesamt}] {args.task}/{args.variant} run {run} session {sid}")

    for erg in messlauf.fahre(out, auftrag, args.repeat, ClaudeAusfuehrung(), melde=melde):
        if erg.verworfen:
            print(f"  {erg.verworfen} - Lauf wird nicht verbucht.")
            continue
        print(f"  gewichtet {erg.record['weighted_tokens']:,}".replace(",", ".")
              + f" Tokens, {erg.record['duration_s']} s -> {erg.pfad}")
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    project = Path(args.project or os.getcwd()).resolve()
    out = Path(args.out)
    try:
        measured = measure_session(project, args.session_id)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    run = args.run or runs.next_run_index(out, args.task, args.variant)
    env = {"round": args.round or date.today().isoformat(), "model": args.model,
           "cli_version": cli_version(), "prompt_sha": None}
    rec = runs.build_record(task=args.task, variant=args.variant, run=run, project=project,
                             outcome=args.outcome, note=args.note, measured=measured, env=env)
    print(f"verbucht: {runs.write_record(out, rec)}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    p = runs.record_path(Path(args.out), args.task, args.variant, args.run)
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
    recs = runs.load_records(Path(args.out), args.task)
    if args.round:
        recs = [r for r in recs if r.get("round") == args.round]
    if not recs:
        print(f"Keine Laufdaten unter {args.out}.")
        return 1
    summary = summarize(recs)
    baselines, notes = resolve_baselines(Path(args.out), summary, args.baseline)
    persist_baseline(Path(args.out), baselines, args.baseline)
    attach_verdicts(summary, baselines, strict_round=not args.across_rounds)
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json
          else report(summary, baselines))
    for n in notes:
        print(n)
    if args.across_rounds:
        print("\n! --across-rounds: Laeufe aus verschiedenen Messrunden stehen hier "
              "gegeneinander. Das Urteil ist eine Orientierung, kein Beleg.")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    recs = runs.load_records(Path(args.out), args.task)
    if not recs:
        print(f"Keine Laufdaten unter {args.out}.")
        return 1
    summary = summarize(recs, group_round=True)
    baselines, notes = resolve_baselines(Path(args.out), summary, args.baseline)
    persist_baseline(Path(args.out), baselines, args.baseline)
    attach_verdicts(summary, baselines)
    trends = trend(summary)
    if args.json:
        print(json.dumps({"runden": summary, "verlauf": trends}, ensure_ascii=False, indent=2))
    else:
        print(report(summary, baselines, show_round=True))
        print(render_trend(trends))
    for n in notes:
        print(n)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if args.plan_cmd == "list":
        found = plans.list_plans(out)
        if not found:
            print(f"Keine Messplaene unter {plans.plans_dir(out)}.")
            return 1
        for p in found:
            varianten = ", ".join(sorted(p.get("variants") or {})) or "-"
            print(f"{p['task']}: Varianten [{varianten}], Basis {p.get('baseline') or '-'}, "
                  f"Modell {p.get('model') or '-'}, "
                  f"zuletzt {p.get('updated_at') or p.get('created_at')}")
        return 0

    plan = plans.load_plan(out, args.task)
    if args.plan_cmd == "show":
        if not plan:
            print(f"Kein Messplan fuer '{args.task}' unter {plans.plans_dir(out)}.")
            return 1
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    # save: legt an oder aktualisiert, ohne dass dafuer gemessen werden muss.
    plan = plan or plans.new_plan(args.task)
    for k in plans.PLAN_OPTIONS:
        if (val := getattr(args, k, None)) is not None:
            plan[k] = str(Path(val).resolve()) if k in ("prompt_file", "project") else val
    if plan.get("prompt_file") and Path(plan["prompt_file"]).is_file():
        plan["prompt_sha"] = plans.prompt_sha(
            Path(plan["prompt_file"]).read_text(encoding="utf-8"))
    if note := plans.record_baseline(plan, args.baseline):
        print(note)
    if args.variant:
        if note := plans.record_variant(plan, args.variant, args.setup):
            print(note)
    print(f"gespeichert: {plans.save_plan(out, plan)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(default_out()), help="Ablage der Laufdaten")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--task", required=True, help="Kennung der Testaufgabe")
        p.add_argument("--variant", required=True, help="Kennung der Variante")
        # Default None statt cwd: nur so laesst sich "nicht angegeben" von "bewusst gesetzt"
        # unterscheiden - und nur dann darf ein Messplan den Wert beisteuern.
        p.add_argument("--project", help="Arbeitsverzeichnis des Laufs (Default: cwd/Messplan)")
        p.add_argument("--outcome", choices=OUTCOMES, default="unset", help="Ertrag des Laufs")
        p.add_argument("--note", default="", help="Freitext zum Lauf")
        p.add_argument("--round", help="Messrunde (Default: heutiges Datum). Nur innerhalb "
                                       "einer Runde wird ein Urteil gefaellt.")

    r = sub.add_parser("run", help="Laeufe headless ausfuehren und verbuchen")
    common(r)
    r.add_argument("--prompt", help="Testaufgabe als Text")
    r.add_argument("--prompt-file", help="Testaufgabe aus Datei (identisch fuer alle Varianten)")
    r.add_argument("--repeat", type=int, default=3, help="Anzahl Laeufe (Default 3)")
    r.add_argument("--setup", help="Shell-Kommando vor jedem Lauf, z. B. Variante einspielen")
    r.add_argument("--model", help="Modell fuer den Lauf")
    r.add_argument("--permission-mode", help="Default acceptEdits")
    r.add_argument("--timeout", type=int, help="Sekunden pro Lauf (Default 900)")
    r.add_argument("--no-plan", action="store_true",
                   help="gespeicherten Messplan ignorieren und nicht fortschreiben")
    r.set_defaults(func=cmd_run)

    m = sub.add_parser("measure", help="bereits gelaufene Session verbuchen")
    common(m)
    m.add_argument("--session-id", required=True)
    m.add_argument("--run", type=int, help="Laufnummer (Default: naechste freie)")
    m.add_argument("--model", help="Modell des Laufs, fuer die Vergleichbarkeit")
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
    c.add_argument("--round", help="nur diese Messrunde")
    c.add_argument("--across-rounds", action="store_true",
                   help="Urteil auch ueber Messrunden hinweg faellen (nicht belastbar)")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_compare)

    h = sub.add_parser("history", help="Verlauf einer Testaufgabe ueber mehrere Messrunden")
    h.add_argument("--task", help="nur diese Testaufgabe")
    h.add_argument("--baseline", help="Variante, gegen die je Runde verglichen wird")
    h.add_argument("--json", action="store_true")
    h.set_defaults(func=cmd_history)

    pl = sub.add_parser("plan", help="Messdefinition speichern, ansehen, auflisten")
    plsub = pl.add_subparsers(dest="plan_cmd", required=True)
    for name, hint in (("save", "anlegen oder aendern"), ("show", "anzeigen")):
        sp = plsub.add_parser(name, help=hint)
        sp.add_argument("--task", required=True)
        if name == "save":
            sp.add_argument("--prompt-file", help="Datei mit der Testaufgabe")
            sp.add_argument("--project", help="Arbeitsverzeichnis der Laeufe")
            sp.add_argument("--model")
            sp.add_argument("--permission-mode")
            sp.add_argument("--timeout", type=int)
            sp.add_argument("--baseline", help="Variante, gegen die verglichen wird")
            sp.add_argument("--variant", help="Variante, deren Umschaltung festgehalten wird")
            sp.add_argument("--setup", help="Umschaltkommando dieser Variante")
    plsub.add_parser("list", help="alle Messplaene")
    pl.set_defaults(func=cmd_plan)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
