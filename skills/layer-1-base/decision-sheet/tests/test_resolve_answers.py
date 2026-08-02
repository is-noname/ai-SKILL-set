#!/usr/bin/env python3
"""Tests fuer resolve_answers.py - stdlib only (kein pytest noetig).

    python3 -m unittest discover skills/layer-1-base/decision-sheet/tests
    python3 skills/layer-1-base/decision-sheet/tests/test_resolve_answers.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import resolve_answers as ra  # noqa: E402

SHEET = [
    {"v": 1, "sheet": "demo", "title": "Demo"},
    {"id": 1, "q": "Counter oder Timestamp?", "t": "pick", "o": ["Counter", "Timestamp"], "d": "Counter"},
    {"id": 2, "q": "Registry global lassen?", "t": "yn", "d": "y"},
    {"id": 3, "q": "Wie heisst der Archiv-Ordner?", "t": "text"},
    {"id": 4, "q": "Wer darf schreiben?", "t": "multi", "o": ["claude", "codex", "vibe"], "d": ["claude", "codex"]},
    {"id": 5, "q": "flock oder mkdir?", "t": "pick", "o": ["flock", "mkdir"], "d": "flock", "dep": [1, "Counter"]},
]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def aufloesen(self, answers: dict, sheet: list[dict] | None = None) -> ra.Aufloesung:
        sheet_path = self.dir / "demo.jsonl"
        sheet_path.write_text(
            "\n".join(json.dumps(o) for o in (sheet or SHEET)) + "\n", encoding="utf-8"
        )
        ans_path = self.dir / "demo.answers.json"
        ans_path.write_text(json.dumps({"sheet": "demo", "a": answers}), encoding="utf-8")
        return ra.resolve_all(sheet_path, ans_path)

    def frage(self, res: ra.Aufloesung, qid: str) -> ra.Entscheidung:
        return next(e for e in res.entscheidungen if e.id == qid)


class TestInterpretation(Base):
    """Die sieben Regeln, die frueher als Prosa in SKILL.md standen."""

    def test_leere_map_alles_empfehlung(self):
        res = self.aufloesen({})
        for qid in ("1", "2", "4", "5"):
            e = self.frage(res, qid)
            self.assertEqual(e.herkunft, ra.EMPFEHLUNG, qid)
            self.assertFalse(e.braucht_antwort, qid)
        self.assertEqual(self.frage(res, "1").wert, "Counter")
        self.assertEqual(self.frage(res, "4").wert, ["claude", "codex"])

    def test_yn_default_normalisiert(self):
        self.assertEqual(self.frage(self.aufloesen({}), "2").wert, "ja")

    def test_abweichende_antwort_ist_gewaehlt(self):
        e = self.frage(self.aufloesen({"1": "Timestamp"}), "1")
        self.assertEqual((e.wert, e.herkunft), ("Timestamp", ra.GEWAEHLT))

    def test_leeres_multi_array_ist_echte_antwort(self):
        e = self.frage(self.aufloesen({"4": []}), "4")
        self.assertEqual(e.wert, [])
        self.assertEqual(e.herkunft, ra.GEWAEHLT)
        self.assertFalse(e.braucht_antwort)

    def test_antwort_plus_notiz(self):
        e = self.frage(self.aufloesen({"1": {"a": "Timestamp", "n": "NFS pruefen"}}), "1")
        self.assertEqual((e.wert, e.herkunft, e.notiz), ("Timestamp", ra.GEWAEHLT, "NFS pruefen"))
        self.assertFalse(e.braucht_antwort)

    def test_null_mit_notiz_braucht_antwort(self):
        e = self.frage(self.aufloesen({"1": {"a": None, "n": "was heisst hier kollisionsfrei?"}}), "1")
        self.assertTrue(e.braucht_antwort)
        self.assertEqual(e.notiz, "was heisst hier kollisionsfrei?")
        # Die Empfehlung gilt weiter als Vorschlag, ist aber nicht bestaetigt.
        self.assertEqual(e.wert, "Counter")
        self.assertEqual(e.herkunft, ra.EMPFEHLUNG)

    def test_frage_ohne_default_und_ohne_antwort_ist_offen(self):
        e = self.frage(self.aufloesen({}), "3")
        self.assertEqual((e.wert, e.herkunft), (None, ra.OFFEN))
        self.assertTrue(e.braucht_antwort)

    def test_dep_erfuellt_bleibt_drin(self):
        res = self.aufloesen({})
        self.assertEqual(res.entfallen, [])
        self.assertEqual(self.frage(res, "5").wert, "flock")

    def test_dep_nicht_erfuellt_faellt_raus(self):
        res = self.aufloesen({"1": "Timestamp"})
        self.assertEqual(res.entfallen, ["5"])
        self.assertNotIn("5", [e.id for e in res.entscheidungen])

    def test_antwort_gleich_empfehlung_bleibt_empfehlung(self):
        # Kommt nur mit Notiz vor - der Renderer laesst den Eintrag sonst weg.
        e = self.frage(self.aufloesen({"1": {"a": "Counter", "n": "bestaetigt"}}), "1")
        self.assertEqual(e.herkunft, ra.EMPFEHLUNG)
        self.assertFalse(e.braucht_antwort)


class TestKanten(Base):
    def test_dep_kette_bricht_bei_unsichtbarem_elternteil(self):
        sheet = SHEET + [{"id": 6, "q": "Lock-Timeout?", "t": "text", "dep": [5, "flock"]}]
        res = self.aufloesen({"1": "Timestamp"}, sheet)
        self.assertEqual(sorted(res.entfallen), ["5", "6"])

    def test_dep_zyklus_haengt_nicht(self):
        sheet = [
            {"sheet": "demo"},
            {"id": 1, "q": "A?", "t": "yn", "d": "y", "dep": [2, "ja"]},
            {"id": 2, "q": "B?", "t": "yn", "d": "y", "dep": [1, "ja"]},
        ]
        self.assertEqual(len(self.aufloesen({}, sheet).entscheidungen), 2)

    def test_dep_auf_yn_vergleicht_normalisiert(self):
        sheet = [
            {"sheet": "demo"},
            {"id": 1, "q": "Registry global?", "t": "yn", "d": "y"},
            {"id": 2, "q": "Pfad?", "t": "text", "d": "~/ai-shared", "dep": [1, "y"]},
        ]
        res = self.aufloesen({}, sheet)
        self.assertEqual(res.entfallen, [])

    def test_dep_liste_von_werten(self):
        sheet = [
            {"sheet": "demo"},
            {"id": 1, "q": "Backend?", "t": "pick", "o": ["a", "b", "c"], "d": "c"},
            {"id": 2, "q": "Detail?", "t": "text", "d": "x", "dep": [1, ["a", "b"]]},
        ]
        self.assertEqual(self.aufloesen({}, sheet).entfallen, ["2"])
        self.assertEqual(self.aufloesen({"1": "b"}, sheet).entfallen, [])

    def test_unbekannte_id_wird_gemeldet(self):
        res = self.aufloesen({"99": "irgendwas"})
        self.assertEqual(res.unbekannte_ids, ["99"])

    def test_slug_mismatch_ist_fehler(self):
        sheet_path = self.dir / "demo.jsonl"
        sheet_path.write_text("\n".join(json.dumps(o) for o in SHEET), encoding="utf-8")
        ans = self.dir / "x.answers.json"
        ans.write_text(json.dumps({"sheet": "anderes", "a": {}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            ra.resolve_all(sheet_path, ans)

    def test_kaputtes_json_wirft_valueerror_kein_systemexit(self):
        sheet_path = self.dir / "demo.jsonl"
        sheet_path.write_text('{"sheet":"demo"}\n{"id":1,,}\n', encoding="utf-8")
        ans = self.dir / "demo.answers.json"
        ans.write_text('{"sheet":"demo","a":{}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            ra.resolve_all(sheet_path, ans)

    def test_antwortdatei_ohne_a_wirft_valueerror(self):
        sheet_path = self.dir / "demo.jsonl"
        sheet_path.write_text("\n".join(json.dumps(o) for o in SHEET), encoding="utf-8")
        ans = self.dir / "demo.answers.json"
        ans.write_text('{"sheet":"demo"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            ra.resolve_all(sheet_path, ans)

    def test_schmale_schnittstelle_gibt_liste(self):
        sheet_path = self.dir / "demo.jsonl"
        sheet_path.write_text("\n".join(json.dumps(o) for o in SHEET), encoding="utf-8")
        ans = self.dir / "demo.answers.json"
        ans.write_text('{"sheet":"demo","a":{}}', encoding="utf-8")
        out = ra.resolve(sheet_path, ans)
        self.assertIsInstance(out, list)
        self.assertTrue(all(isinstance(e, ra.Entscheidung) for e in out))


class TestReport(Base):
    def test_report_markiert_offene(self):
        text = ra.format_report(self.aufloesen({"1": {"a": None, "n": "Rueckfrage"}}))
        self.assertIn("ACHTUNG", text)
        self.assertIn("Rueckfrage", text)
        self.assertIn("#1", text)

    def test_report_ohne_offene_meldet_vollstaendig(self):
        sheet = [o for o in SHEET if o.get("id") != 3]  # die Frage ohne Default raus
        self.assertIn("Alle aktiven Fragen sind entschieden.",
                      ra.format_report(self.aufloesen({}, sheet)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
