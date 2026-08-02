#!/usr/bin/env python3
"""Loest Sheet + Antwort-Datei zur tatsaechlichen Entscheidung je Frage auf.

Die exportierte .answers.json ist absichtlich komprimiert: uebernommene
Empfehlungen fallen weg, ausgefilterte dep-Fragen tauchen nie auf. Damit ist sie
allein bedeutungslos - erst zusammen mit dem Sheet ergibt sie eine Entscheidung.
Diese Umkehrung stand frueher als Prosa in der SKILL.md und wurde vom Agenten
jedes Mal neu im Kopf ausgefuehrt; hier ist sie Code.

Reine Funktionen, kein SystemExit: bei kaputten Eingaben fliegt ein ValueError.

Usage (auch direkt aufrufbar, gibt die Tabelle aus):
    python3 resolve_answers.py .decisions/<slug>.jsonl .decisions/<slug>.answers.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Herkunft eines Werts.
EMPFEHLUNG = "empfehlung"
GEWAEHLT = "gewaehlt"
OFFEN = "offen"

_MISSING = object()


@dataclass
class Entscheidung:
    """Was fuer eine Frage tatsaechlich gilt - Sheet und Antwort zusammengefuehrt."""

    id: str
    frage: str
    typ: str
    wert: Any
    herkunft: str
    notiz: str = ""
    braucht_antwort: bool = False
    empfehlung: Any = None


@dataclass
class Aufloesung:
    """Ergebnis fuer ein ganzes Sheet."""

    sheet: str
    title: str
    entscheidungen: list[Entscheidung] = field(default_factory=list)
    entfallen: list[str] = field(default_factory=list)
    unbekannte_ids: list[str] = field(default_factory=list)

    @property
    def offene(self) -> list[Entscheidung]:
        return [e for e in self.entscheidungen if e.braucht_antwort]


# ---------- Parsen ----------


def _normalize_yn(value: Any) -> Any:
    """'y'/'yes'/'ja'/true -> 'ja', alles andere -> 'nein' (wie im Renderer)."""
    return "ja" if str(value).lower() in ("y", "yes", "ja", "true") else "nein"


def parse_sheet(text: str) -> tuple[dict, list[dict]]:
    """Zerlegt ein Sheet in (Header, Fragen). Erwartet ein JSON-Objekt pro Zeile."""
    objs: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            objs.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Zeile {lineno} ist kein gueltiges JSON: {exc}") from exc
    if not objs:
        raise ValueError("Sheet ist leer.")

    head = objs.pop(0) if "id" not in objs[0] else {}
    if not objs:
        raise ValueError("Sheet enthaelt nur einen Header, keine Fragen.")

    for q in objs:
        if q.get("id") in (None, ""):
            raise ValueError(f"Frage ohne 'id': {q}")
        q["id"] = str(q["id"])
        if q.get("t") == "yn" and "d" in q:
            q["d"] = _normalize_yn(q["d"])
    return head, objs


def parse_answers(text: str) -> tuple[str, dict[str, Any]]:
    """Zerlegt eine Antwort-Datei in (Sheet-Slug, {id: rohwert})."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Antwort-Datei ist kein gueltiges JSON: {exc}") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("a"), dict):
        raise ValueError('Antwort-Datei hat kein Feld "a" mit einer Map.')
    return str(obj.get("sheet") or ""), {str(k): v for k, v in obj["a"].items()}


# ---------- Aufloesen ----------


def _split(raw: Any) -> tuple[Any, str]:
    """{"a":wert,"n":notiz} -> (wert, notiz); alles andere ist der Wert selbst.

    Ein Objekt statt eines [wert, notiz]-Tupels, weil eine multi-Antwort
    ["claude","codex"] sonst nicht von Antwort-plus-Notiz zu trennen waere.
    """
    if isinstance(raw, dict):
        return raw.get("a", None), str(raw.get("n") or "").strip()
    return raw, ""


def _is_answer(value: Any) -> bool:
    """Leerstring, None und 'nicht da' sind keine Antwort - False und 0 schon."""
    return value is not _MISSING and value is not None and value != ""


def _effective(q: dict, answered: dict[str, Any]) -> Any:
    """Gewaehlter Wert, sonst die Empfehlung, sonst None (offen)."""
    val = answered.get(q["id"], _MISSING)
    if _is_answer(val):
        return val
    return q.get("d", None)


def _visible(q: dict, by_id: dict[str, dict], answered: dict[str, Any], seen: set[str]) -> bool:
    """dep-Filter, identisch zur visible()-Logik im Renderer.

    seen bricht Ringe ab - ein Zyklus wuerde die Rekursion sonst nie beenden.
    """
    dep = q.get("dep")
    if not dep:
        return True
    if q["id"] in seen:
        return True
    seen = seen | {q["id"]}
    if not isinstance(dep, (list, tuple)) or len(dep) != 2:
        raise ValueError(f"Frage #{q['id']} hat ein defektes 'dep' - erwartet [id, wert].")
    dq = by_id.get(str(dep[0]))
    if dq is None:
        return True
    if not _visible(dq, by_id, answered, seen):
        return False
    got = _effective(dq, answered)
    wants = dep[1] if isinstance(dep[1], list) else [dep[1]]
    if dq.get("t") == "yn":
        wants = [_normalize_yn(w) for w in wants]
    if isinstance(got, list):
        return any(g in wants for g in got)
    return got in wants


def resolve_all(sheet_path: Path | str, answers_path: Path | str) -> Aufloesung:
    """Sheet + Antworten -> Aufloesung mit Entscheidungen, Entfallenen und Unbekannten."""
    sheet_path, answers_path = Path(sheet_path), Path(answers_path)
    head, qs = parse_sheet(sheet_path.read_text(encoding="utf-8"))
    slug, raw_answers = parse_answers(answers_path.read_text(encoding="utf-8"))

    sheet_slug = str(head.get("sheet") or sheet_path.stem)
    if slug and sheet_slug and slug != sheet_slug:
        raise ValueError(
            f"Antworten gehoeren zu Sheet '{slug}', das Sheet ist '{sheet_slug}'."
        )

    answered: dict[str, Any] = {}
    notes: dict[str, str] = {}
    for qid, raw in raw_answers.items():
        val, note = _split(raw)
        answered[qid] = val
        if note:
            notes[qid] = note

    by_id = {q["id"]: q for q in qs}
    res = Aufloesung(sheet=sheet_slug, title=str(head.get("title") or sheet_slug))
    res.unbekannte_ids = [qid for qid in raw_answers if qid not in by_id]

    for q in qs:
        qid = q["id"]
        if not _visible(q, by_id, answered, set()):
            res.entfallen.append(qid)
            continue

        given = answered.get(qid, _MISSING)
        note = notes.get(qid, "")
        wert = _effective(q, answered)

        if _is_answer(given):
            # Der Renderer laesst uebernommene Empfehlungen weg - steht der Wert
            # trotzdem drin (weil eine Notiz dranhaengt), ist es keine Abweichung.
            herkunft = EMPFEHLUNG if _same(given, q.get("d")) else GEWAEHLT
        elif _is_answer(wert):
            herkunft = EMPFEHLUNG
        else:
            herkunft = OFFEN

        # a:null mit Notiz ist die teuerste Stelle des Formats: keine Auswahl, nur
        # ein Kommentar - meist eine Rueckfrage, die vor dem Umsetzen zu klaeren ist.
        offene_rueckfrage = qid in raw_answers and not _is_answer(given) and bool(note)

        res.entscheidungen.append(
            Entscheidung(
                id=qid,
                frage=str(q.get("q", "")),
                typ=str(q.get("t", "pick")),
                wert=wert,
                herkunft=herkunft,
                notiz=note,
                braucht_antwort=herkunft == OFFEN or offene_rueckfrage,
                empfehlung=q.get("d", None),
            )
        )
    return res


def resolve(sheet_path: Path | str, answers_path: Path | str) -> list[Entscheidung]:
    """Schmale Schnittstelle: nur die Entscheidungen der sichtbaren Fragen."""
    return resolve_all(sheet_path, answers_path).entscheidungen


def _same(a: Any, b: Any) -> bool:
    """Wertgleichheit wie im Renderer (JSON-Vergleich, bei multi also reihenfolgetreu)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---------- Ausgabe ----------


def _fmt(value: Any) -> str:
    if value is None:
        return "OFFEN"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "(nichts davon)"
    if isinstance(value, bool):
        return "ja" if value else "nein"
    return str(value)


LABEL = {EMPFEHLUNG: "Empfehlung", GEWAEHLT: "gewaehlt", OFFEN: "offen"}


def format_report(res: Aufloesung) -> str:
    """Menschen- und agentenlesbare Tabelle einer Aufloesung."""
    lines = [f"Entscheidungen aus Sheet '{res.sheet}' ({len(res.entscheidungen)} aktive Fragen):", ""]
    for e in res.entscheidungen:
        mark = "!" if e.braucht_antwort else " "
        label = LABEL[e.herkunft]
        if e.braucht_antwort and e.herkunft == EMPFEHLUNG:
            label = "Empfehlung, nicht bestaetigt - Rueckfrage offen"
        lines.append(f"{mark} #{e.id}  {e.frage}")
        lines.append(f"     -> {_fmt(e.wert)}   [{label}]")
        if e.notiz:
            lines.append(f"     Notiz: {e.notiz}")
    lines.append("")

    if res.entfallen:
        lines.append(
            f"Entfallen (dep nicht erfuellt): {', '.join('#' + i for i in res.entfallen)}"
        )
    if res.unbekannte_ids:
        lines.append(
            "Antworten zu unbekannten ids (Sheet nachtraeglich geaendert?): "
            + ", ".join("#" + i for i in res.unbekannte_ids)
        )
    offen = res.offene
    if offen:
        lines.append(
            f"ACHTUNG: {len(offen)} Frage(n) ohne belastbare Entscheidung - "
            f"vor dem Umsetzen klaeren: " + ", ".join("#" + e.id for e in offen)
        )
    else:
        lines.append("Alle aktiven Fragen sind entschieden.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    try:
        print(format_report(resolve_all(argv[0], argv[1])))
    except (OSError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
