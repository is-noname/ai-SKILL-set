#!/usr/bin/env python3
"""Die Darstellung - macht aus beurteilten Werten Markdown, und sonst nichts.

Die Trennung Wert/Darstellung ist der Grund, warum `--json` und die Markdown-Tabelle
dieselbe Entscheidung tragen: hier wird kein Urteil gefaellt, hier wird eines gelesen.
Jede Zeile bekommt ihr Urteil bereits fertig aus `verdict.py` und wird nur noch in einen
deutschen Satz gesetzt. Wer hier eine Regel einbaut, hat zwei Wahrheiten im Skill.

Dies ist auch die einzige Stelle, an der aus englischen Codenamen deutsche Woerter
werden - `KIND_TEXT` uebersetzt die Urteilsart, sonst nichts.
"""

from __future__ import annotations

from typing import Any

import runs
import verdict

# Urteilsart -> das Wort, das im Report steht. Die einzige Sprachgrenze des Skills.
KIND_TEXT = {"cheaper": "guenstiger", "costlier": "teurer"}


def render_verdict(v: dict[str, Any]) -> str:
    """Rendert einen Urteilswert als deutschen Satz - Wortlaut zeichengleich zur Vorversion."""
    kind = v["kind"]
    if kind == "baseline":
        return "Basis"
    if kind == "no-data":
        return "keine Daten"
    if kind == "task-changed":
        return "Testaufgabe geaendert - nicht vergleichbar"
    if kind == "model-mixed":
        return "verschiedene Modelle (" + ", ".join(v["models"]) + ") - nicht vergleichbar"
    if kind == "rounds-mixed":
        return "verschiedene Messrunden - Basis neu messen"
    if kind == "outcome-open":
        return "Ertrag offen"
    extra = f", n={v['n_variant']} - ungesichert" if v.get("thin") else ""
    if kind == "no-difference":
        return f"kein belastbarer Unterschied (Spannen ueberlappen{extra})"
    wort = KIND_TEXT[kind]
    if v["delta"] is None:
        return f"{wort} (Basis-Median 0{extra})"
    return f"{wort} um {abs(v['delta']) * 100:.0f} %" + (f" ({extra.lstrip(', ')})" if extra else "")


def render_table(summary: dict["verdict.Key", dict[str, Any]],
                 baseline: "verdict.Baseline" = None, show_round: bool = False) -> str:
    """Die Vergleichstabelle je Testaufgabe. `summary` ist eine beurteilte Tabelle."""
    by_task: dict[str, list[dict[str, Any]]] = {}
    for s in summary.values():
        by_task.setdefault(s["task"], []).append(s)

    out: list[str] = ["# Benchmark"]
    for task, variants in sorted(by_task.items()):
        variants.sort(key=lambda v: ((v.get("round") or ""), v["variant"]))
        base_name = verdict.select_base(variants, baseline)

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
            outcome = ", ".join(f"{k}:{n}" for k, n in sorted(v["outcomes"].items()))
            verdict_text = render_verdict(v["verdict"])
            prefix = f"| {v.get('round') or '-'} " if show_round else ""
            out.append(
                prefix + f"| {v['variant']} | {v['n']} | {med} | {span} | "
                f"{v['cost_median'] if v['cost_median'] is not None else '-'} | "
                f"{v['turns_median'] if v['turns_median'] is not None else '-'} | "
                f"{v['cache_hit_median'] * 100:.0f} % | {outcome} | {verdict_text} |")

    out += ["", f"Gewichtung: " + ", ".join(f"{k} x{w}" for k, w in runs.WEIGHTS.items()) + ".",
            "Tool-Result-Tokens sind aus der Zeichenlaenge geschaetzt, die usage-Werte sind exakt."]
    return "\n".join(out)


def render_trend(trends: dict["verdict.Key", list[dict[str, Any]]]) -> str:
    if not trends:
        return ("\n## Verlauf\n\nNur eine Messrunde vorhanden - kein Verlauf. "
                "Fuer den Vergleich ueber die Zeit dieselbe Variante in einer zweiten "
                "Runde erneut messen (`--round`).")
    out = ["", "## Verlauf ueber die Messrunden", "",
           "Beobachtung mit Datum, kein Beleg: zwischen den Runden liegt mehr als die "
           "Optimierung. Belastbar ist nur ein Urteil innerhalb einer Runde."]
    for key, series in sorted(trends.items()):
        out += ["", f"**{key.task} / {key.variant}**", ""]
        for p in series:
            med = f"{p['weighted_median']:,}".replace(",", ".")
            d = (f" ({p['delta_to_prev_round'] * 100:+.0f} %)"
                 if p["delta_to_prev_round"] is not None else "")
            warn = "  <- Modell/CLI gewechselt" if p["env_changed"] else ""
            out.append(f"- {p['round']}: {med} gew. Tokens (n={p['n']}){d}{warn}")
    return "\n".join(out)
