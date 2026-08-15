#!/usr/bin/env python3
"""Das Urteil - der fachliche Kern des Skills, ohne Dateisystem und ohne Darstellung.

Hier steht die eine Frage, um derer willen ueberhaupt gemessen wird: *hat die Optimierung
etwas gebracht, und darf man das ueberhaupt sagen?* Alles, was diese Frage beantwortet -
Zusammenfassung der Laeufe, Vergleichbarkeitspruefung, Urteilsregel, Basiswahl, Verlauf -
liegt in diesem Modul. Wie ein Urteil aussieht, wenn es jemand liest, gehoert nach
`report.py`; wo die Laufdaten herkommen, nach `runs.py`.

Der Einstieg ist `judge()`: Laufdatensaetze und eine Basis herein, fertig beurteilte
Tabelle heraus. Die uebrigen Namen sind die Schritte dieses einen Wegs - wer sie einzeln
ruft, prueft eine einzelne Regel, nicht das Zusammenspiel.

Die Begriffe sind englisch, das Glossar in SKILL.md nennt je Begriff den Codenamen:
Basis = baseline, Ertrag = outcome, Spanne = range, Messrunde = round, Urteil = verdict.
Deutsch wird erst, was jemand liest - das steht in `report.py`.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Die Basis: je Testaufgabe eine Variante, oder keine. Kommt immer aus
# plans.resolve_baselines() - Kommandozeile schlaegt Messplan schlaegt Alphabet.
Baseline = "Mapping[str, str | None] | None"


@dataclass(frozen=True, order=True)
class Key:
    """Der Gruppenschluessel von Tabelle und Verlauf: Testaufgabe, Variante, Messrunde.

    Ein Wert statt eines zusammengesetzten Strings - `task::round::variant` liesse sich
    nicht mehr eindeutig zerlegen, sobald ein Variantenname selbst '::' enthaelt. Der
    String entsteht erst dort, wo JSON ihn verlangt (`as_string()`), nicht hier.
    """

    task: str
    variant: str
    round: str | None = None

    def as_string(self) -> str:
        if self.round is None:
            return f"{self.task}::{self.variant}"
        return f"{self.task}::{self.round}::{self.variant}"


def to_json(grouped: dict["Key", Any]) -> dict[str, Any]:
    """Wandelt einen Key-gruppierten Wert an den Rand: JSON verlangt String-Schluessel."""
    return {k.as_string(): v for k, v in grouped.items()}


def _distinct(group: list[dict[str, Any]], field_name: str) -> list[str]:
    """Die belegten Werte eines Umgebungsfelds. Unbekannt (None) zaehlt nicht als Abweichung."""
    return sorted({r[field_name] for r in group if r.get(field_name)})


def summarize(recs: list[dict[str, Any]],
              group_round: bool = False) -> dict[Key, dict[str, Any]]:
    """Fasst die Laeufe je (Task, Variante) zusammen - bei group_round zusaetzlich je Messrunde.

    task/variant sind laut Schema (runs.build_record) in jedem Datensatz gesetzt - hier direkt
    indiziert. Die uebrigen Felder bleiben ueber .get()/is-not-None defensiv, weil Altdaten aus
    frueheren Laeufen im Ablageverzeichnis liegen koennen, die vor diesem Schema entstanden sind.

    Modell, CLI-Version, Messrunde und Aufgaben-Pruefsumme werden als Mengen mitgefuehrt, nicht
    als Einzelwerte: eine Variante, die aus zwei Modellen zusammengesetzt ist, hat kein Modell -
    sie hat ein Problem, und verdict_for() muss das sehen koennen.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for r in recs:
        rnd = (r.get("round") or "ohne-runde") if group_round else ""
        groups.setdefault((r["task"], rnd, r["variant"]), []).append(r)

    summary: dict[Key, dict[str, Any]] = {}
    for (task, rnd, variant), group in groups.items():
        weighted = [r["weighted_tokens"] for r in group if r.get("weighted_tokens") is not None]
        costs = [r["cost_usd"] for r in group if r.get("cost_usd") is not None]
        turns = [r["num_turns"] for r in group if r.get("num_turns") is not None]
        outcomes = Counter(r.get("outcome", "unset") for r in group)
        key = Key(task, variant, rnd if group_round else None)
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
        return {"kind": "task-changed", "shas": sorted(shas)}
    models = set(base.get("models") or []) | set(other.get("models") or [])
    if len(models) > 1:
        return {"kind": "model-mixed", "models": sorted(models)}
    if strict_round:
        rounds = set(base.get("rounds") or []) | set(other.get("rounds") or [])
        if len(rounds) > 1:
            return {"kind": "rounds-mixed", "rounds": sorted(rounds)}
    return None


def verdict_for(base: dict[str, Any], other: dict[str, Any],
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
        return {"kind": "baseline"}
    if base.get("weighted_median") is None or other.get("weighted_median") is None:
        return {"kind": "no-data"}
    if blocker := comparability(base, other, strict_round):
        return blocker
    if other["outcomes"].get("fail") or other["outcomes"].get("unset"):
        return {"kind": "outcome-open", "outcomes": dict(other["outcomes"])}
    # n < 3 sperrt das Urteil nicht mehr, es kennzeichnet es. Bei einem Lauf ist die
    # Spanne ein Punkt - Spannen koennen dann nicht ueberlappen, also faellt das Urteil
    # immer, auch wenn der Unterschied reine Streuung ist. Deshalb "thin".
    thin = base["n"] < 3 or other["n"] < 3
    evidence = {"thin": thin, "n_baseline": base["n"], "n_variant": other["n"]}
    overlap = not (other["weighted_max"] < base["weighted_min"]
                   or other["weighted_min"] > base["weighted_max"])
    if overlap:
        return {"kind": "no-difference", **evidence,
                "baseline_range": [base["weighted_min"], base["weighted_max"]],
                "variant_range": [other["weighted_min"], other["weighted_max"]]}
    if base["weighted_median"] == 0:
        # Basis-Median 0: eine Prozentangabe waere eine Division durch 0.
        return {"kind": "costlier", "delta": None, **evidence,
                "baseline_median": 0, "variant_median": other["weighted_median"]}
    delta = (other["weighted_median"] - base["weighted_median"]) / base["weighted_median"]
    return {"kind": "cheaper" if delta < 0 else "costlier", "delta": round(delta, 4), **evidence,
            "baseline_median": base["weighted_median"], "variant_median": other["weighted_median"]}


def select_base(variants: list[dict[str, Any]], baseline: Baseline) -> str:
    variants = sorted(variants, key=lambda v: v["variant"])
    wanted = (baseline or {}).get(variants[0]["task"])
    if wanted and any(v["variant"] == wanted for v in variants):
        return wanted
    return variants[0]["variant"]


def attach_verdicts(summary: dict[Key, dict[str, Any]], baseline: Baseline,
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
            v["verdict"] = verdict_for(base, v, strict_round)


def trend(summary: dict[Key, dict[str, Any]]) -> dict[Key, list[dict[str, Any]]]:
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

    result: dict[Key, list[dict[str, Any]]] = {}
    for (task, variant), points in by_variant.items():
        if len(points) < 2:
            continue
        points.sort(key=lambda p: p["round"])
        series = []
        for i, p in enumerate(points):
            prev = points[i - 1] if i else None
            delta = None
            if prev and prev["weighted_median"]:
                delta = round((p["weighted_median"] - prev["weighted_median"])
                              / prev["weighted_median"], 4)
            series.append({
                "round": p["round"], "weighted_median": p["weighted_median"],
                "n": p["n"], "delta_to_prev_round": delta,
                "models": p["models"], "cli_versions": p["cli_versions"],
                "env_changed": bool(
                    prev and (set(p["models"]) != set(prev["models"])
                              or set(p["cli_versions"]) != set(prev["cli_versions"]))),
            })
        result[Key(task, variant)] = series
    return result


@dataclass(frozen=True)
class Judgement:
    """Das Ergebnis einer Auswertung: beurteilte Tabelle, dazu der Verlauf ueber die Runden.

    `table` traegt je Zeile das Feld `verdict` - der Wert aus verdict_for(), nicht sein Satz.
    `history` ist nur bei einer Auswertung je Messrunde belegt; ohne Rundentrennung gibt es
    keinen Zeitpunkt, ueber den etwas verlaufen koennte.
    """

    table: dict[Key, dict[str, Any]]
    history: dict[Key, list[dict[str, Any]]] = field(default_factory=dict)


def judge(recs: list[dict[str, Any]], baseline: Baseline = None, *,
          per_round: bool = False, strict_round: bool = True) -> Judgement:
    """Laufdatensaetze und eine Basis herein, fertig beurteilte Tabelle heraus.

    Der eine Einstieg ins Urteil. Die Reihenfolge - zusammenfassen, Basis je Gruppe waehlen,
    urteilen, bei Rundentrennung den Verlauf ziehen - ist keine Aufrufer-Entscheidung: eine
    Tabelle ohne Urteil oder ein Urteil gegen die falsche Basis sieht genauso plausibel aus
    wie eine richtige, und genau deshalb liegt die Reihenfolge hier statt im CLI.

    `per_round` trennt die Laeufe zusaetzlich nach Messrunde und fuellt `history`.
    `strict_round` gibt die Rundensperre frei (`--across-rounds`) - das Urteil ist dann
    eine Orientierung, kein Beleg.
    """
    summary = summarize(recs, group_round=per_round)
    attach_verdicts(summary, baseline, strict_round=strict_round)
    return Judgement(table=summary, history=trend(summary) if per_round else {})
