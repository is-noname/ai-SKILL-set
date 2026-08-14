#!/usr/bin/env python3
"""Die Regeln des Sheet-Formats - einmal, als Daten.

Vorher standen sie dreimal da: validate() in render_sheet.py, parseSheet() im
Renderer und die Feldreferenz in SKILL.md. Sie sind auseinandergedriftet - dep-Zyklen
und der ctx-Typ wurden nur in Python geprueft, die yn-Normalisierung gab es nur im
Renderer. Hier stehen die Regeln als Daten (FIELDS, MESSAGES, NORMALIZE); Python und
JS sind nur noch zwei duenne Schleifen darueber. Der Renderer bekommt die Spec beim
Rendern in die HTML injiziert und kennt sie nicht selbst.

Fehler werden gesammelt, nicht geworfen: check() gibt eine Liste zurueck, damit der
Aufrufer entscheidet, was ein Abbruch ist. Nur was das Zerlegen unmoeglich macht
(kaputtes JSON, leeres Sheet) ist ein SheetError.

Die Meldungen tragen Umlaute: sie landen sowohl im Terminal als auch im Browser und
sind das Einzige, was der User vom Format zu sehen bekommt.

Usage:
    python3 sheet_spec.py --json     # Laufzeit-Spec (das, was in die HTML wandert)
    python3 sheet_spec.py --fields   # Feldreferenz-Tabelle fuer SKILL.md
    python3 sheet_spec.py --sync     # Spec-Block in assets/index.html aktualisieren
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION = 1
DEFAULT_TYPE = "pick"
TYPES = ["pick", "multi", "yn", "text"]

# yn hat keine Optionen im Sheet - der Renderer setzt diese beiden ein, und ein
# 'd' wird auf genau diese Labels normalisiert (siehe NORMALIZE).
YN_OPTIONS = ["ja", "nein"]

NORMALIZE = {
    "yn": {
        "field": "d",
        "truthy": ["y", "yes", "ja", "true", "1"],
        "labels": YN_OPTIONS,
    }
}

# Ein Eintrag pro Feld - Reihenfolge = Pruefreihenfolge = Reihenfolge in der
# Feldreferenz. 'kind' waehlt die Pruefung, 'msg_*' die Meldung dazu.
FIELDS: list[dict[str, Any]] = [
    {
        "name": "id",
        "kind": "id",
        "required": True,
        "pflicht": "ja",
        "doc": "Sprechender Kurzname, eindeutig — keine durchlaufende Zahl (Einschub wuerde sonst alle folgenden IDs verschieben)",
    },
    {
        "name": "q",
        "kind": "text",
        "required": True,
        "msg_missing": "missing_q",
        "msg_invalid": "invalid_q",
        "pflicht": "ja",
        "doc": "Fragetext, eine Zeile",
    },
    {
        "name": "t",
        "kind": "enum",
        "values": TYPES,
        "msg_invalid": "invalid_t",
        "pflicht": "nein",
        "doc": "`pick` (default) · `multi` · `yn` · `text`",
    },
    {
        "name": "o",
        "kind": "options",
        "required_for": ["pick", "multi"],
        "msg_missing": "missing_o",
        "msg_invalid": "invalid_o",
        "pflicht": "bei `pick`/`multi`",
        "doc": "Optionen. Bei `yn` implizit ja/nein",
    },
    {
        "name": "d",
        "kind": "any",
        "pflicht": "nein",
        "doc": (
            "**Empfehlung** — im Renderer vorausgewählt und als `EMPF` markiert. "
            "Bei `yn`: `\"y\"`/`\"n\"`. Bei `multi`: Array"
        ),
    },
    {
        "name": "why",
        "kind": "string",
        "msg_invalid": "invalid_string",
        "pflicht": "nein",
        "doc": "Eine Zeile Begründung/Trade-off unter der Frage",
    },
    {
        "name": "ctx",
        "kind": "string",
        "msg_invalid": "invalid_string",
        "pflicht": "nein",
        "doc": (
            "Längerer Hintergrund zu **dieser einen Frage** — im Renderer eingeklappt "
            "hinter „+ Kontext\", nicht standardmäßig sichtbar. Nicht zu verwechseln mit "
            "dem Header-`ctx` (Dokumentverweis fürs ganze Sheet)"
        ),
    },
    {
        "name": "dep",
        "kind": "dep",
        "msg_invalid": "invalid_dep",
        "pflicht": "nein",
        "doc": (
            "`[id, wert]` oder `[id, [wert1, wert2]]` — Frage wird nur aktiv, wenn die "
            "andere so beantwortet ist"
        ),
    },
]

MESSAGES = {
    "json": "Zeile {line} ist kein gültiges JSON: {detail}",
    "empty": "Sheet ist leer.",
    "not_object": "Zeile {line} ist kein JSON-Objekt.",
    "head_is_question": "Erste Zeile sieht aus wie eine Frage, hat aber keine 'id'.",
    "only_head": "Sheet enthält nur einen Header, keine Fragen.",
    "missing_id": "Frage ohne 'id': {value}",
    "dup_id": "Doppelte id '{id}'.",
    "missing_q": "Frage #{id} hat keinen Fragetext ('q').",
    "invalid_q": "Frage #{id}: 'q' muss ein String sein.",
    "invalid_t": "Frage #{id}: Typ '{value}' — erlaubt: {allowed}.",
    "missing_o": "Frage #{id} ist '{type}', hat aber keine Optionen ('o').",
    "invalid_o": "Frage #{id}: 'o' muss eine nicht-leere Liste sein.",
    "missing_field": "Frage #{id}: Feld '{field}' fehlt.",
    "invalid_field": "Frage #{id}: Feld '{field}' ist ungültig.",
    "invalid_string": "Frage #{id}: '{field}' muss ein String sein.",
    "invalid_dep": "Frage #{id} hat ein defektes 'dep' — erwartet [id, wert].",
    "unknown_dep": "Frage #{id} hängt an unbekannter id '{value}'.",
    "dep_cycle": "dep-Zyklus über Frage #{id}.",
}

HEADER_FIELDS = [
    ("v", "Format-Version, aktuell 1"),
    ("sheet", "Slug = Dateiname ohne Endung"),
    ("title", "Überschrift im Renderer"),
    ("ctx", "Pfad zum Dokument mit dem Hintergrund, optional"),
]

SPEC_BLOCK_RE = re.compile(
    r'(<script id="sheet-spec" type="application/json">)(.*?)(</script>)', re.S
)


class SheetError(Exception):
    """Das Sheet laesst sich nicht einmal zerlegen - hier gibt es nichts zu sammeln."""


class _Loose(dict):
    """Fehlende Platzhalter bleiben stehen, statt einen KeyError zu werfen."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def msg(key: str, **vals: Any) -> str:
    return MESSAGES[key].format_map(_Loose(vals))


# ---------- Spec fuer den Renderer ----------


def runtime_spec() -> dict:
    """Was der Renderer braucht - ohne die Doku-Texte, die nur SKILL.md fuellen."""
    fields = [{k: v for k, v in f.items() if k not in ("doc", "pflicht")} for f in FIELDS]
    return {
        "version": VERSION,
        "default_type": DEFAULT_TYPE,
        "types": TYPES,
        "yn_options": YN_OPTIONS,
        "normalize": NORMALIZE,
        "fields": fields,
        "messages": MESSAGES,
    }


def spec_json(indent: int | None = None) -> str:
    return json.dumps(runtime_spec(), ensure_ascii=False, indent=indent, sort_keys=False)


def inject(html: str) -> str:
    """Ersetzt den Spec-Block in einer index.html durch die aktuelle Spec.

    Fehlt der Block (alter globaler Spiegel), bleibt die HTML unveraendert - der
    Renderer laeuft dann ohne Vorab-Pruefung weiter, statt gar nicht zu laden.
    """
    return SPEC_BLOCK_RE.sub(lambda m: m.group(1) + "\n" + spec_json() + "\n" + m.group(3), html)


def extract(html: str) -> dict | None:
    m = SPEC_BLOCK_RE.search(html)
    return json.loads(m.group(2)) if m else None


# ---------- Zerlegen ----------


def parse_lines(text: str) -> tuple[dict, list[dict]]:
    """Zerlegt ein Sheet in (Header, Fragen). Ein JSON-Objekt pro Zeile."""
    objs: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SheetError(msg("json", line=lineno, detail=exc)) from exc
        if not isinstance(obj, dict):
            raise SheetError(msg("not_object", line=lineno))
        objs.append(obj)
    if not objs:
        raise SheetError(msg("empty"))

    head = objs.pop(0) if "id" not in objs[0] else {}
    if head.get("q"):
        raise SheetError(msg("head_is_question"))
    if not objs:
        raise SheetError(msg("only_head"))
    return head, objs


def normalize(questions: list[dict]) -> list[dict]:
    """Vereinheitlicht in-place, was sonst jede Seite fuer sich auslegen muesste."""
    for q in questions:
        if q.get("id") is not None:
            q["id"] = str(q["id"])
        rule = NORMALIZE.get(str(q.get("t", DEFAULT_TYPE)))
        if rule and rule["field"] in q:
            value = str(q[rule["field"]]).lower()
            q[rule["field"]] = rule["labels"][0 if value in rule["truthy"] else 1]
    return questions


# ---------- Pruefen ----------


def _empty(value: Any) -> bool:
    """Leer im Sinne der Spec - False und 0 sind Werte, keine Luecken."""
    return value is None or value == "" or (isinstance(value, (list, dict)) and len(value) == 0)


def _check_field(q: dict, qid: str, qtype: str, field: dict, ids: set[str]) -> list[str]:
    name = field["name"]
    value = q.get(name)
    required = field.get("required", False) or qtype in field.get("required_for", [])
    if _empty(value):
        if required:
            return [msg(field.get("msg_missing", "missing_field"), id=qid, field=name, type=qtype)]
        return []

    kind = field["kind"]
    bad = field.get("msg_invalid", "invalid_field")
    if kind in ("text", "string"):
        if not isinstance(value, str):
            return [msg(bad, id=qid, field=name, value=value)]
    elif kind == "enum":
        if value not in field["values"]:
            return [msg(bad, id=qid, field=name, value=value, allowed=", ".join(field["values"]))]
    elif kind == "options":
        if not isinstance(value, list):
            return [msg(bad, id=qid, field=name, value=value)]
    elif kind == "dep":
        if not isinstance(value, list) or len(value) != 2:
            return [msg(bad, id=qid, field=name, value=value)]
        if str(value[0]) not in ids:
            return [msg("unknown_dep", id=qid, field=name, value=value[0])]
    return []


def _check_cycles(questions: list[dict]) -> list[str]:
    """Der Renderer wertet dep rekursiv aus - ein Ring haengt den Browser auf."""
    parent = {
        str(q["id"]): str(q["dep"][0])
        for q in questions
        if q.get("id") is not None and isinstance(q.get("dep"), list) and len(q["dep"]) == 2
    }
    errors, reported = [], set()
    for start in parent:
        if start in reported:
            continue
        path, cur = {start}, parent[start]
        while cur in parent:
            if cur in path:
                # Ein Ring, eine Meldung: alle beteiligten Fragen gelten als gemeldet.
                reported |= path
                errors.append(msg("dep_cycle", id=cur))
                break
            path.add(cur)
            cur = parent[cur]
    return errors


def check(questions: list[dict]) -> list[str]:
    """Duenne Schleife ueber FIELDS - gibt alle Fehler zurueck, nicht nur den ersten."""
    errors: list[str] = []
    ids: set[str] = set()
    valid: list[dict] = []
    for q in questions:
        raw_id = q.get("id")
        qid = "" if raw_id is None else str(raw_id).strip()
        if not qid:
            # Kompakt wie JSON.stringify im Renderer - die Meldung soll beidseitig
            # zeichengleich sein.
            errors.append(
                msg("missing_id", value=json.dumps(q, ensure_ascii=False, separators=(",", ":")))
            )
            continue
        if qid in ids:
            errors.append(msg("dup_id", id=qid))
            continue
        ids.add(qid)
        valid.append(q)

    for q in valid:
        qid = str(q["id"])
        qtype = str(q.get("t", DEFAULT_TYPE))
        for field in FIELDS:
            if field["kind"] == "id":
                continue
            errors.extend(_check_field(q, qid, qtype, field, ids))
    errors.extend(_check_cycles(valid))
    return errors


def load(text: str) -> tuple[dict, list[dict], list[str]]:
    """Zerlegen, pruefen, normalisieren - der uebliche Weg in den Skripten."""
    head, questions = parse_lines(text)
    errors = check(questions)
    normalize(questions)
    return head, questions, errors


# ---------- Feldreferenz fuer SKILL.md ----------


def field_reference() -> str:
    """Die Tabelle aus SKILL.md - generiert, damit sie nicht parallel gepflegt wird."""
    rows = ["| Feld | Pflicht | Bedeutung |", "|------|---------|-----------|"]
    rows += [f"| `{f['name']}` | {f['pflicht']} | {f['doc']} |" for f in FIELDS]
    header = ", ".join(f"`{name}` ({doc})" for name, doc in HEADER_FIELDS)
    rows += ["", f"Header: {header}."]
    return "\n".join(rows)


def _template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "index.html"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "--json"
    if mode == "--json":
        print(spec_json(indent=2))
    elif mode == "--fields":
        print(field_reference())
    elif mode == "--sync":
        path = _template_path()
        html = path.read_text(encoding="utf-8")
        new = inject(html)
        if new == html:
            print(f"unveraendert: {path}")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"aktualisiert: {path}")
    else:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
