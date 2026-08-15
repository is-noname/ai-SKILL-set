#!/usr/bin/env python3
"""Tests fuer locate.py - stdlib only (kein pytest noetig).

locate.py traegt die Lade-Mechanik, die konsumierende Skills frueher jeweils
selbst hielten (IZG-T-146). Geprueft wird, dass sie unter eindeutigem
Modulnamen laedt, Wiederholungen nicht doppelt ausfuehrt und Interface-Drift
beim Re-Export als ImportError meldet - nicht erst spaeter als AttributeError.

    python3 -m unittest discover skills/layer-1-base/izg-transcript-reader/tests
    python3 skills/layer-1-base/izg-transcript-reader/tests/test_locate.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import locate  # noqa: E402


class Load(unittest.TestCase):
    def test_laedt_transcript_per_default(self):
        module = locate.load()
        self.assertTrue(hasattr(module, "read_session"))

    def test_registriert_unter_eigenem_namen_nicht_als_transcript(self):
        locate.load("transcript")
        self.assertIn(f"{locate.MODULE_PREFIX}.transcript", sys.modules)

    def test_zweiter_aufruf_liefert_dieselbe_instanz(self):
        self.assertIs(locate.load(), locate.load())

    def test_unbekanntes_modul_nennt_erwarteten_pfad(self):
        with self.assertRaises(ImportError) as ctx:
            locate.load("gibtsnicht")
        self.assertIn("gibtsnicht.py", str(ctx.exception))


class ReExport(unittest.TestCase):
    def test_uebernimmt_namen_ins_zielnamespace(self):
        ns = {}
        locate.re_export(ns, ["CHARS_PER_TOKEN", "read_session"])
        self.assertEqual(ns["CHARS_PER_TOKEN"], locate.load().CHARS_PER_TOKEN)
        self.assertTrue(callable(ns["read_session"]))

    def test_gibt_quellmodul_zurueck(self):
        self.assertIs(locate.re_export({}, []), locate.load())

    def test_unbekannter_name_meldet_interface_drift(self):
        with self.assertRaises(ImportError) as ctx:
            locate.re_export({}, ["gibt_es_nicht"])
        self.assertIn("gibt_es_nicht", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
