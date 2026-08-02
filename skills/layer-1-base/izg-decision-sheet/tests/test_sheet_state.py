#!/usr/bin/env python3
"""Tests fuer sheet_state.py - stdlib only (kein pytest noetig).

Geprueft wird der Lebenszyklus, nicht die Dateiformate: was wartet, was ist durch,
was geht nach einer Korrektur wieder auf. Die Nanosekunden-Falle (Korrektur in
derselben Sekunde wie der Stempel) steht hier als Test statt als Kommentar im Hook.

    python3 -m unittest discover skills/layer-1-base/izg-decision-sheet/tests
    python3 skills/layer-1-base/izg-decision-sheet/tests/test_sheet_state.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sheet_state  # noqa: E402

HEAD = '{"v":1,"sheet":"demo","title":"Demo"}'
QUESTION = '{"id":1,"q":"Counter oder Timestamp?","o":["Counter","Timestamp"]}'


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        self.decisions = self.project / ".decisions"
        self.decisions.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def write_sheet(self, slug: str = "demo", *, mtime_ns: int | None = None) -> Path:
        path = self.decisions / f"{slug}.jsonl"
        path.write_text(f"{HEAD}\n{QUESTION}\n", encoding="utf-8")
        if mtime_ns is not None:
            os.utime(path, ns=(mtime_ns, mtime_ns))
        return path

    def write_answers(self, slug: str = "demo", *, mtime_ns: int | None = None) -> Path:
        path = self.decisions / f"{slug}.answers.json"
        path.write_text('{"sheet":"%s","a":{}}' % slug, encoding="utf-8")
        if mtime_ns is not None:
            os.utime(path, ns=(mtime_ns, mtime_ns))
        return path


class Pending(Base):
    def test_kein_ordner_kein_sheet(self):
        leer = Path(self._tmp.name) / "anderes-projekt"
        leer.mkdir()
        self.assertIsNone(sheet_state.pending(leer))

    def test_frisches_sheet_wartet(self):
        path = self.write_sheet()
        found = sheet_state.pending(self.project)
        self.assertIsNotNone(found)
        self.assertEqual(found.path, path.resolve())
        self.assertEqual(found.slug, "demo")

    def test_gestempeltes_sheet_wartet_nicht_mehr(self):
        self.write_sheet()
        sheet_state.mark_opened(sheet_state.pending(self.project))
        self.assertIsNone(sheet_state.pending(self.project))

    def test_antwort_neuer_als_sheet_ist_durch(self):
        self.write_sheet(mtime_ns=1_000_000_000_000_000_000)
        self.write_answers(mtime_ns=1_000_000_000_000_000_001)
        self.assertIsNone(sheet_state.pending(self.project))

    def test_aeltere_antwort_zaehlt_nicht(self):
        # Sheet nach dem Beantworten ueberarbeitet: die alte Antwort gilt nicht mehr.
        self.write_answers(mtime_ns=1_000_000_000_000_000_000)
        self.write_sheet(mtime_ns=1_000_000_000_000_000_001)
        self.assertIsNotNone(sheet_state.pending(self.project))

    def test_neuestes_sheet_zuerst(self):
        self.write_sheet("alt", mtime_ns=1_000_000_000_000_000_000)
        self.write_sheet("neu", mtime_ns=2_000_000_000_000_000_000)
        self.assertEqual(sheet_state.pending(self.project).slug, "neu")

    def test_naechstes_sheet_wenn_das_neueste_durch_ist(self):
        self.write_sheet("alt", mtime_ns=1_000_000_000_000_000_000)
        self.write_sheet("neu", mtime_ns=2_000_000_000_000_000_000)
        sheet_state.mark_opened(sheet_state.pending(self.project))
        self.assertEqual(sheet_state.pending(self.project).slug, "alt")


class Stempel(Base):
    def test_korrektur_in_derselben_sekunde_geht_wieder_auf(self):
        """Die Nanosekunden-Falle: mit Sekunden-Aufloesung bliebe das Fenster zu.

        Ein defektes Sheet wird gestempelt (sonst wiederholt es seine Fehlermeldung
        in jedem Turn) und sofort korrigiert - beides faellt in dieselbe Sekunde.
        """
        base = 1_000_000_000_000_000_000  # exakt auf der Sekundengrenze
        path = self.write_sheet(mtime_ns=base)
        sheet_state.mark_opened(sheet_state.pending(self.project))
        self.assertIsNone(sheet_state.pending(self.project))

        os.utime(path, ns=(base + 500, base + 500))  # halbe Mikrosekunde spaeter
        found = sheet_state.pending(self.project)
        self.assertIsNotNone(found, "korrigiertes Sheet muss wieder aufgehen")
        self.assertEqual(found.mtime_ns, base + 500)

    def test_stempel_waechst_nicht(self):
        path = self.write_sheet(mtime_ns=1_000_000_000_000_000_000)
        for i in range(3):
            os.utime(path, ns=(1_000_000_000_000_000_000 + i, 1_000_000_000_000_000_000 + i))
            sheet_state.mark_opened(sheet_state.pending(self.project))
        stamp = sheet_state.stamp_path(self.project).read_text(encoding="utf-8")
        self.assertEqual(len(stamp.strip().splitlines()), 1)

    def test_zweites_sheet_verdraengt_das_erste_nicht(self):
        self.write_sheet("eins", mtime_ns=1_000_000_000_000_000_000)
        self.write_sheet("zwei", mtime_ns=2_000_000_000_000_000_000)
        sheet_state.mark_opened(sheet_state.pending(self.project))  # zwei
        sheet_state.mark_opened(sheet_state.pending(self.project))  # eins
        self.assertIsNone(sheet_state.pending(self.project))

    def test_nicht_schreibbares_projekt_meldet_false(self):
        self.write_sheet()
        sheet = sheet_state.pending(self.project)
        os.chmod(self.decisions, 0o500)
        self.addCleanup(os.chmod, self.decisions, 0o700)
        if os.access(self.decisions, os.W_OK):
            self.skipTest("laeuft als root - Schreibschutz greift nicht")
        self.assertFalse(sheet_state.mark_opened(sheet))


class Pfade(Base):
    def test_project_of_ueber_decisions(self):
        path = self.write_sheet()
        self.assertEqual(sheet_state.project_of(path), self.project.resolve())

    def test_project_of_ohne_decisions(self):
        lose = self.project / "demo.jsonl"
        lose.write_text(HEAD + "\n", encoding="utf-8")
        self.assertEqual(sheet_state.project_of(lose), self.project.resolve())

    def test_answers_pfad(self):
        self.write_sheet()
        sheet = sheet_state.pending(self.project)
        self.assertEqual(sheet.answers.name, "demo.answers.json")


class CLI(Base):
    def test_pending_gibt_pfad_aus(self):
        path = self.write_sheet()
        from io import StringIO

        buf, sys.stdout = sys.stdout, StringIO()
        try:
            rc = sheet_state.main(["pending", str(self.project)])
            out = sys.stdout.getvalue().strip()
        finally:
            sys.stdout = buf
        self.assertEqual(rc, 0)
        self.assertEqual(out, str(path.resolve()))

    def test_pending_ohne_sheet_ist_rc1(self):
        self.assertEqual(sheet_state.main(["pending", str(self.project)]), 1)

    def test_mark_opened_ueber_cli(self):
        path = self.write_sheet()
        self.assertEqual(sheet_state.main(["mark-opened", str(path)]), 0)
        self.assertIsNone(sheet_state.pending(self.project))

    def test_unbekanntes_kommando(self):
        self.assertEqual(sheet_state.main(["quatsch", "x"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
