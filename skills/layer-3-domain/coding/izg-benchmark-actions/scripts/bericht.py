#!/usr/bin/env python3
"""Die Darstellung - macht aus beurteilten Werten Markdown, und sonst nichts.

Die Trennung Wert/Darstellung ist der Grund, warum `--json` und die Markdown-Tabelle
dieselbe Entscheidung tragen: hier wird kein Urteil gefaellt, hier wird eines gelesen.
Jede Zeile bekommt ihr Urteil bereits fertig aus `urteil.py` und wird nur noch in einen
deutschen Satz gesetzt. Wer hier eine Regel einbaut, hat zwei Wahrheiten im Skill.
"""

from __future__ import annotations

from typing import Any

import runs
import urteil


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


def report(summary: dict[str, dict[str, Any]], baseline: "urteil.Basis" = None,
           show_round: bool = False) -> str:
    """Die Vergleichstabelle je Testaufgabe. `summary` ist eine beurteilte Tabelle."""
    by_task: dict[str, list[dict[str, Any]]] = {}
    for s in summary.values():
        by_task.setdefault(s["task"], []).append(s)

    out: list[str] = ["# Benchmark"]
    for task, variants in sorted(by_task.items()):
        variants.sort(key=lambda v: ((v.get("round") or ""), v["variant"]))
        base_name = urteil.select_base(variants, baseline)

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
            urteilstext = render_verdict(v["urteil"])
            prefix = f"| {v.get('round') or '-'} " if show_round else ""
            out.append(
                prefix + f"| {v['variant']} | {v['n']} | {med} | {span} | "
                f"{v['cost_median'] if v['cost_median'] is not None else '-'} | "
                f"{v['turns_median'] if v['turns_median'] is not None else '-'} | "
                f"{v['cache_hit_median'] * 100:.0f} % | {ertrag} | {urteilstext} |")

    out += ["", f"Gewichtung: " + ", ".join(f"{k} x{w}" for k, w in runs.WEIGHTS.items()) + ".",
            "Tool-Result-Tokens sind aus der Zeichenlaenge geschaetzt, die usage-Werte sind exakt."]
    return "\n".join(out)


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
