#!/usr/bin/env python3
"""Tests fuer verdict() und seine Darstellung - stdlib only (kein pytest noetig).

Kein Dateisystem, kein HOME-Zugriff, kein claude-Aufruf: die Summary-Zeilen werden
von Hand gebaut statt ueber load_records()/measure_session() erzeugt. Getestet wird
die Regel selbst - n >= 3, kein Urteil bei offenem Ertrag, kein Ausweichen auf
Mediane bei ueberlappenden Spannen - und dass sie in Markdown wie in JSON exakt
dieselbe Entscheidung traegt.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_verdict.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bench  # noqa: E402


def mk(variant: str, n: int, median: int | None, wmin: int | None, wmax: int | None,
       outcomes: dict[str, int] | None = None, task: str = "t1") -> dict:
    return {
        "task": task, "variant": variant, "n": n,
        "weighted_median": median, "weighted_min": wmin, "weighted_max": wmax,
        "cost_median": None, "turns_median": None, "cache_hit_median": 0.0,
        "outcomes": outcomes if outcomes is not None else {"ok": n},
    }


class Verdict(unittest.TestCase):
    def test_basis_gegen_sich_selbst(self):
        base = mk("basis", 3, 150, 100, 200)
        self.assertEqual(bench.verdict(base, base), {"art": "basis"})

    def test_keine_daten_bei_fehlendem_median(self):
        base = mk("basis", 3, 150, 100, 200)
        other = mk("neu", 0, None, None, None, outcomes={})
        self.assertEqual(bench.verdict(base, other)["art"], "keine-daten")

    def test_median_null_ist_kein_fehlender_wert(self):
        base = mk("basis", 3, 0, 0, 0)
        other = mk("neu", 3, 500, 400, 600)
        v = bench.verdict(base, other)
        self.assertNotEqual(v["art"], "keine-daten")
        self.assertEqual(v["art"], "teurer")
        self.assertIsNone(v["delta"])
        self.assertEqual(bench.render_verdict(v), "teurer (Basis-Median 0)")

    def test_n_gleich_zwei_gegen_drei(self):
        base = mk("basis", 3, 150, 100, 200)
        other = mk("neu", 2, 400, 380, 420)
        v = bench.verdict(base, other)
        self.assertEqual(v["art"], "zu-wenige-laeufe")
        self.assertEqual((v["n_basis"], v["n_variante"]), (3, 2))

    def test_einzelner_unset_lauf_macht_ertrag_offen(self):
        base = mk("basis", 3, 150, 100, 200)
        other = mk("neu", 3, 400, 380, 420, outcomes={"ok": 2, "unset": 1})
        self.assertEqual(bench.verdict(base, other)["art"], "ertrag-offen")

    def test_fail_lauf_macht_ertrag_offen(self):
        base = mk("basis", 3, 150, 100, 200)
        other = mk("neu", 3, 400, 380, 420, outcomes={"ok": 2, "fail": 1})
        self.assertEqual(bench.verdict(base, other)["art"], "ertrag-offen")

    def test_spannen_ueberlappen_um_genau_ein_token(self):
        base = mk("basis", 3, 150, 100, 200)
        other = mk("neu", 3, 250, 200, 300)  # 200 liegt in beiden Spannen
        v = bench.verdict(base, other)
        self.assertEqual(v["art"], "kein-unterschied")
        self.assertEqual(bench.render_verdict(v), "kein belastbarer Unterschied (Spannen ueberlappen)")

    def test_spannen_exakt_buendig_ohne_ueberlappung(self):
        base = mk("basis", 3, 150, 100, 200)
        other = mk("neu", 3, 250, 201, 300)  # direkt anschliessend, kein gemeinsamer Wert
        v = bench.verdict(base, other)
        self.assertEqual(v["art"], "teurer")
        self.assertAlmostEqual(v["delta"], (250 - 150) / 150, places=4)

    def test_guenstiger_bei_niedrigerem_median(self):
        base = mk("basis", 3, 400, 380, 420)
        other = mk("neu", 3, 200, 180, 220)
        v = bench.verdict(base, other)
        self.assertEqual(v["art"], "guenstiger")
        self.assertLess(v["delta"], 0)
        self.assertTrue(bench.render_verdict(v).startswith("guenstiger um "))


class AttachUndReport(unittest.TestCase):
    def test_attach_verdicts_setzt_basis_und_urteil_je_variante(self):
        summary = {
            "t1::basis": mk("basis", 3, 150, 100, 200),
            "t1::neu": mk("neu", 3, 250, 201, 300),
        }
        bench.attach_verdicts(summary, baseline="basis")
        self.assertEqual(summary["t1::basis"]["urteil"]["art"], "basis")
        self.assertEqual(summary["t1::neu"]["urteil"]["art"], "teurer")

    def test_report_rendert_median_null_als_zahl_nicht_als_strich(self):
        summary = {
            "t1::basis": mk("basis", 3, 0, 0, 0),
            "t1::neu": mk("neu", 3, 500, 400, 600),
        }
        bench.attach_verdicts(summary, baseline="basis")
        text = bench.report(summary, baseline="basis")
        self.assertIn("| basis | 3 | 0 |", text)
        self.assertIn("Basis |", text)

    def test_report_markdown_zeichengleich_ausserhalb_median_null(self):
        summary = {
            "t1::basis": mk("basis", 3, 150, 100, 200),
            "t1::neu": mk("neu", 3, 250, 201, 300),
        }
        bench.attach_verdicts(summary, baseline="basis")
        text = bench.report(summary, baseline="basis")
        self.assertIn("| basis | 3 | 150 | 100-200 | - | - | 0 % | ok:3 | Basis |", text)
        self.assertIn("teurer um 67 %", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
