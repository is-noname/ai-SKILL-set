#!/usr/bin/env python3
"""Das Urteil - der fachliche Kern des Skills, ohne Dateisystem und ohne Darstellung.

Hier steht die eine Frage, um derer willen ueberhaupt gemessen wird: *hat die Optimierung
etwas gebracht, und darf man das ueberhaupt sagen?* Alles, was diese Frage beantwortet -
Zusammenfassung der Laeufe, Vergleichbarkeitspruefung, Urteilsregel, Basiswahl, Verlauf -
liegt in diesem Modul. Wie ein Urteil aussieht, wenn es jemand liest, gehoert nach
`bericht.py`; wo die Laufdaten herkommen, nach `runs.py`.

Der Einstieg ist `beurteile()`: Laufdatensaetze und eine Basis herein, fertig beurteilte
Tabelle heraus. Die uebrigen Namen sind die Schritte dieses einen Wegs - wer sie einzeln
ruft, prueft eine einzelne Regel, nicht das Zusammenspiel.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Die Basis: je Testaufgabe eine Variante, oder keine. Kommt immer aus
# plans.resolve_baselines() - Kommandozeile schlaegt Messplan schlaegt Alphabet.
Basis = "Mapping[str, str | None] | None"


@dataclass(frozen=True, order=True)
class Kennung:
    """Der Gruppenschluessel von Tabelle und Verlauf: Testaufgabe, Variante, Messrunde.

    Ein Wert statt eines zusammengesetzten Strings - `task::runde::variante` liesse sich
    nicht mehr eindeutig zerlegen, sobald ein Variantenname selbst '::' enthaelt. Der
    String entsteht erst dort, wo JSON ihn verlangt (`als_string()`), nicht hier.
    """

    task: str
    variante: str
    runde: str | None = None

    def als_string(self) -> str:
        if self.runde is None:
            return f"{self.task}::{self.variante}"
        return f"{self.task}::{self.runde}::{self.variante}"


def zu_json(gruppiert: dict["Kennung", Any]) -> dict[str, Any]:
    """Wandelt einen Kennung-gruppierten Wert an den Rand: JSON verlangt String-Schluessel."""
    return {k.als_string(): v for k, v in gruppiert.items()}


def _distinct(group: list[dict[str, Any]], field_name: str) -> list[str]:
    """Die belegten Werte eines Umgebungsfelds. Unbekannt (None) zaehlt nicht als Abweichung."""
    return sorted({r[field_name] for r in group if r.get(field_name)})


def summarize(recs: list[dict[str, Any]],
              group_round: bool = False) -> dict[Kennung, dict[str, Any]]:
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

    summary: dict[Kennung, dict[str, Any]] = {}
    for (task, rnd, variant), group in groups.items():
        weighted = [r["weighted_tokens"] for r in group if r.get("weighted_tokens") is not None]
        costs = [r["cost_usd"] for r in group if r.get("cost_usd") is not None]
        turns = [r["num_turns"] for r in group if r.get("num_turns") is not None]
        outcomes = Counter(r.get("outcome", "unset") for r in group)
        key = Kennung(task, variant, rnd if group_round else None)
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


def select_base(variants: list[dict[str, Any]], baseline: Basis) -> str:
    variants = sorted(variants, key=lambda v: v["variant"])
    wanted = (baseline or {}).get(variants[0]["task"])
    if wanted and any(v["variant"] == wanted for v in variants):
        return wanted
    return variants[0]["variant"]


def attach_verdicts(summary: dict[Kennung, dict[str, Any]], baseline: Basis,
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


def trend(summary: dict[Kennung, dict[str, Any]]) -> dict[Kennung, list[dict[str, Any]]]:
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

    result: dict[Kennung, list[dict[str, Any]]] = {}
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
        result[Kennung(task, variant)] = reihe
    return result


@dataclass(frozen=True)
class Beurteilung:
    """Das Ergebnis einer Auswertung: beurteilte Tabelle, dazu der Verlauf ueber die Runden.

    `tabelle` traegt je Zeile das Feld `urteil` - der Wert aus verdict(), nicht sein Satz.
    `verlauf` ist nur bei einer Auswertung je Messrunde belegt; ohne Rundentrennung gibt es
    keinen Zeitpunkt, ueber den etwas verlaufen koennte.
    """

    tabelle: dict[Kennung, dict[str, Any]]
    verlauf: dict[Kennung, list[dict[str, Any]]] = field(default_factory=dict)


def beurteile(recs: list[dict[str, Any]], baseline: Basis = None, *,
              je_runde: bool = False, strict_round: bool = True) -> Beurteilung:
    """Laufdatensaetze und eine Basis herein, fertig beurteilte Tabelle heraus.

    Der eine Einstieg ins Urteil. Die Reihenfolge - zusammenfassen, Basis je Gruppe waehlen,
    urteilen, bei Rundentrennung den Verlauf ziehen - ist keine Aufrufer-Entscheidung: eine
    Tabelle ohne Urteil oder ein Urteil gegen die falsche Basis sieht genauso plausibel aus
    wie eine richtige, und genau deshalb liegt die Reihenfolge hier statt im CLI.

    `je_runde` trennt die Laeufe zusaetzlich nach Messrunde und fuellt `verlauf`.
    `strict_round` gibt die Rundensperre frei (`--across-rounds`) - das Urteil ist dann
    eine Orientierung, kein Beleg.
    """
    summary = summarize(recs, group_round=je_runde)
    attach_verdicts(summary, baseline, strict_round=strict_round)
    return Beurteilung(tabelle=summary, verlauf=trend(summary) if je_runde else {})
