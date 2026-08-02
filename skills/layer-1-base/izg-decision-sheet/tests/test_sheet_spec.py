#!/usr/bin/env python3
"""Tests fuer sheet_spec.py - stdlib only (kein pytest noetig).

Der Kern ist CASES: eine Tabelle aus kaputten Sheets und der Meldung, die dabei
herauskommen muss. Dieselbe Tabelle laeuft gegen die Python-Schleife und - wenn node
da ist - gegen die JS-Schleife aus assets/index.html. Genau dort sind die beiden
Implementierungen frueher auseinandergedriftet.

    python3 -m unittest discover skills/layer-1-base/izg-decision-sheet/tests
    python3 skills/layer-1-base/izg-decision-sheet/tests/test_sheet_spec.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import sheet_spec  # noqa: E402
import render_sheet  # noqa: E402

HEAD = '{"v":1,"sheet":"demo","title":"Demo"}'


def sheet(*questions: str) -> str:
    return "\n".join([HEAD, *questions]) + "\n"


# (Name, Sheet-Text, erwartete Fehlerliste) - [] heisst: muss sauber durchgehen.
CASES: list[tuple[str, str, list[str]]] = [
    (
        "sauber",
        sheet(
            '{"id":1,"q":"A?","t":"pick","o":["x","y"],"d":"x"}',
            '{"id":2,"q":"B?","t":"yn","d":"y"}',
            '{"id":3,"q":"C?","t":"text"}',
            '{"id":4,"q":"D?","t":"multi","o":["a","b"],"d":["a"]}',
            '{"id":5,"q":"E?","t":"pick","o":["f","m"],"dep":[1,"x"],"ctx":"Hintergrund","why":"kurz"}',
        ),
        [],
    ),
    # --- Drift-Fall 1: dep-Zyklus wurde nur in Python geprueft ---
    (
        "dep-zyklus",
        sheet(
            '{"id":1,"q":"A?","o":["x"],"dep":[2,"y"]}',
            '{"id":2,"q":"B?","o":["y"],"dep":[1,"x"]}',
        ),
        ["dep-Zyklus über Frage #1."],
    ),
    (
        "dep-selbstbezug",
        sheet('{"id":1,"q":"A?","o":["x"],"dep":[1,"x"]}'),
        ["dep-Zyklus über Frage #1."],
    ),
    # --- Drift-Fall 2: ctx-Typ wurde nur in Python geprueft ---
    (
        "ctx-kein-string",
        sheet('{"id":1,"q":"A?","o":["x"],"ctx":{"a":1}}'),
        ["Frage #1: 'ctx' muss ein String sein."],
    ),
    (
        "why-kein-string",
        sheet('{"id":1,"q":"A?","o":["x"],"why":42}'),
        ["Frage #1: 'why' muss ein String sein."],
    ),
    # --- Drift-Fall 3: 'o' war in Python nur "truthy", im Renderer eine Liste ---
    (
        "o-leeres-objekt",
        sheet('{"id":1,"q":"A?","t":"pick","o":{}}'),
        ["Frage #1 ist 'pick', hat aber keine Optionen ('o')."],
    ),
    (
        "o-objekt-mit-inhalt",
        sheet('{"id":1,"q":"A?","t":"pick","o":{"a":1}}'),
        ["Frage #1: 'o' muss eine nicht-leere Liste sein."],
    ),
    (
        "o-leere-liste",
        sheet('{"id":1,"q":"A?","t":"multi","o":[]}'),
        ["Frage #1 ist 'multi', hat aber keine Optionen ('o')."],
    ),
    # --- Struktur und Felder ---
    (
        "doppelte-id",
        sheet('{"id":1,"q":"A?","o":["x"]}', '{"id":1,"q":"B?","o":["y"]}'),
        ["Doppelte id '1'."],
    ),
    (
        "id-fehlt",
        sheet('{"id":1,"q":"A?","o":["x"]}', '{"q":"B?","o":["y"]}'),
        ['Frage ohne \'id\': {"q":"B?","o":["y"]}'],
    ),
    (
        "fragetext-fehlt",
        sheet('{"id":1,"o":["x"]}'),
        ["Frage #1 hat keinen Fragetext ('q')."],
    ),
    (
        "fragetext-kein-string",
        sheet('{"id":1,"q":7,"o":["x"]}'),
        ["Frage #1: 'q' muss ein String sein."],
    ),
    (
        "typ-unbekannt",
        sheet('{"id":1,"q":"A?","t":"radio","o":["x"]}'),
        ["Frage #1: Typ 'radio' — erlaubt: pick, multi, yn, text."],
    ),
    (
        "dep-defekt",
        sheet('{"id":1,"q":"A?","o":["x"],"dep":[1]}'),
        ["Frage #1 hat ein defektes 'dep' — erwartet [id, wert]."],
    ),
    (
        "dep-unbekannt",
        sheet('{"id":1,"q":"A?","o":["x"],"dep":[9,"x"]}'),
        ["Frage #1 hängt an unbekannter id '9'."],
    ),
    (
        "mehrere-fehler-auf-einmal",
        sheet('{"id":1,"q":"A?","t":"pick"}', '{"id":2,"o":["y"],"ctx":5}'),
        [
            "Frage #1 ist 'pick', hat aber keine Optionen ('o').",
            "Frage #2 hat keinen Fragetext ('q').",
            "Frage #2: 'ctx' muss ein String sein.",
        ],
    ),
]

# Strukturfehler: hier bricht schon das Zerlegen ab (SheetError / throw).
FATAL_CASES: list[tuple[str, str, str]] = [
    ("leer", "\n\n", "Sheet ist leer."),
    ("nur-header", HEAD + "\n", "Sheet enthält nur einen Header, keine Fragen."),
    (
        "header-ist-frage",
        '{"q":"A?","o":["x"]}\n{"id":1,"q":"B?","o":["y"]}\n',
        "Erste Zeile sieht aus wie eine Frage, hat aber keine 'id'.",
    ),
    ("kein-objekt", HEAD + "\n[1,2]\n", "Zeile 2 ist kein JSON-Objekt."),
]


def py_errors(text: str) -> list[str]:
    try:
        _head, _qs, errors = sheet_spec.load(text)
    except sheet_spec.SheetError as exc:
        return [str(exc)]
    return errors


class SpecRules(unittest.TestCase):
    """Die Regeltabelle - Python-Seite."""

    def test_cases(self):
        for name, text, expected in CASES:
            with self.subTest(name):
                self.assertEqual(py_errors(text), expected)

    def test_fatal_cases(self):
        for name, text, expected in FATAL_CASES:
            with self.subTest(name):
                self.assertEqual(py_errors(text), [expected])

    def test_kaputtes_json_nennt_die_zeile(self):
        errors = py_errors(HEAD + "\n{kaputt}\n")
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Zeile 2 ist kein gültiges JSON:"), errors[0])

    def test_leerzeilen_verschieben_die_zeilennummer_nicht(self):
        errors = py_errors(HEAD + "\n\n\n{kaputt}\n")
        self.assertTrue(errors[0].startswith("Zeile 4"), errors[0])


class Normalisierung(unittest.TestCase):
    """Drift-Fall 4: das yn-'d' wurde nur im Renderer normalisiert."""

    def test_yn_default_wird_zu_label(self):
        for raw, want in [
            ('"y"', "ja"), ('"yes"', "ja"), ('"ja"', "ja"), ("true", "ja"),
            ('"n"', "nein"), ('"nein"', "nein"), ("false", "nein"),
        ]:
            with self.subTest(raw):
                _head, qs, errors = sheet_spec.load(
                    sheet('{"id":1,"q":"A?","t":"yn","d":' + raw + "}")
                )
                self.assertEqual(errors, [])
                self.assertEqual(qs[0]["d"], want)

    def test_ids_werden_strings(self):
        _head, qs, _errors = sheet_spec.load(sheet('{"id":7,"q":"A?","o":["x"]}'))
        self.assertEqual(qs[0]["id"], "7")

    def test_andere_typen_bleiben_unangetastet(self):
        _head, qs, _errors = sheet_spec.load(
            sheet('{"id":1,"q":"A?","t":"multi","o":["a"],"d":["a"]}')
        )
        self.assertEqual(qs[0]["d"], ["a"])


class RenderSheetWrapper(unittest.TestCase):
    """validate() sammelt statt abzubrechen; der Abbruch ist Sache des CLI."""

    def test_validate_gibt_liste(self):
        self.assertEqual(render_sheet.validate(CASES[0][1]), [])
        self.assertEqual(
            render_sheet.validate(sheet('{"id":1,"q":"A?","t":"pick"}')),
            ["Frage #1 ist 'pick', hat aber keine Optionen ('o')."],
        )

    def test_cli_bricht_ab_und_nennt_alle_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.jsonl"
            path.write_text(CASES[-1][1], encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "render_sheet.py"), str(path), "--no-open"],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            for expected in CASES[-1][2]:
                self.assertIn(expected, proc.stderr)

    def test_gerenderte_html_traegt_die_aktuelle_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.jsonl"
            path.write_text(CASES[0][1], encoding="utf-8")
            out = Path(tmp) / "demo.html"
            # HOME umbiegen: sonst zieht render_sheet den globalen Spiegel heran und
            # der Test misst dessen Alter statt der Vorlage im Skill.
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "render_sheet.py"), str(path),
                 "--no-open", "--out", str(out)],
                capture_output=True, text=True, env={"HOME": tmp, "PATH": os.environ["PATH"]},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(sheet_spec.extract(out.read_text(encoding="utf-8")),
                             sheet_spec.runtime_spec())


class Spiegelungen(unittest.TestCase):
    """Was aus der Spec erzeugt wird, muss zu ihr passen."""

    def test_index_html_hat_die_aktuelle_spec(self):
        html = (SKILL / "assets" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(
            sheet_spec.extract(html), sheet_spec.runtime_spec(),
            "Spec-Block veraltet - 'python3 scripts/sheet_spec.py --sync' laufen lassen",
        )

    def test_skill_md_feldreferenz_stammt_aus_der_spec(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            sheet_spec.field_reference(), text,
            "Feldreferenz veraltet - 'python3 scripts/sheet_spec.py --fields' uebernehmen",
        )


NODE_DRIVER = """
const fs = require('fs');
global.document = { getElementById: () => ({ textContent: fs.readFileSync(process.argv[2], 'utf8') }) };
%(engine)s
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = cases.map(text => {
  try { parseSheet(text); return []; }
  catch (e) { return String(e.message).split("\\n"); }
});
console.log(JSON.stringify(out));
"""


def js_engine_source() -> str:
    """Schneidet die Regel-Schleife aus der index.html - alles vor dem DOM-Teil."""
    html = (SKILL / "assets" / "index.html").read_text(encoding="utf-8")
    js = html.split("<script>\n\"use strict\";", 1)[1]
    start = js.index("/* ============ Format-Regeln")
    end = js.index("function load(")
    return js[start:end]


@unittest.skipUnless(shutil.which("node"), "node nicht installiert")
class RendererGleichPython(unittest.TestCase):
    """Dieselbe Tabelle gegen die JS-Schleife - beide Seiten muessen gleich urteilen."""

    def _run_node(self, texts: list[str]) -> list[list[str]]:
        html = (SKILL / "assets" / "index.html").read_text(encoding="utf-8")
        spec_block = re.search(sheet_spec.SPEC_BLOCK_RE, html).group(2)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "driver.js").write_text(
                NODE_DRIVER % {"engine": js_engine_source()}, encoding="utf-8"
            )
            (tmp / "spec.json").write_text(spec_block, encoding="utf-8")
            (tmp / "cases.json").write_text(json.dumps(texts), encoding="utf-8")
            proc = subprocess.run(
                ["node", str(tmp / "driver.js"), str(tmp / "spec.json"), str(tmp / "cases.json")],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)

    def test_gleiche_meldungen(self):
        cases = CASES + [(n, t, [e]) for n, t, e in FATAL_CASES]
        results = self._run_node([t for _n, t, _e in cases])
        for (name, _text, expected), got in zip(cases, results):
            with self.subTest(name):
                self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
