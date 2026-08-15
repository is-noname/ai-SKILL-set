#!/usr/bin/env python3
"""Tests fuer das Urteil und seine Darstellung - stdlib only (kein pytest noetig).

Kein Dateisystem, kein HOME-Zugriff, kein claude-Aufruf: die Laufdatensaetze werden von
Hand gebaut statt ueber load_records()/measure_session() erzeugt, und alles laeuft durch
den einen Einstieg `verdict.judge()` - Laufdaten und Basis herein, beurteilte Tabelle
heraus. Getestet wird damit die Regel *im Zusammenspiel*: kein Urteil bei offenem Ertrag,
kein Ausweichen auf Mediane bei ueberlappenden Spannen, Vorbehalt statt Sperre bei n < 3 -
und dass sie in Markdown wie in JSON exakt dieselbe Entscheidung traegt.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_verdict.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import report  # noqa: E402
import runs  # noqa: E402
import verdict  # noqa: E402
from verdict import Key  # noqa: E402


def _measured(w: int | None) -> dict:
    return {"session_id": f"s{w}", "requests": 1, "usage": {"input": w or 0},
            "weighted_tokens": w, "raw_tokens": w or 0, "cache_hit_rate": 0.0,
            "tool_calls": {}, "tool_result_tokens": {}, "skills_used": {},
            "subagent_output_tokens": 0, "first_timestamp": "t0", "last_timestamp": "t1"}


def runs_of(variant: str, *weights: int | None, task: str = "t1",
            outcomes: list[str] | None = None) -> list[dict]:
    """Laufdatensaetze einer Variante - ein Datensatz je gewichtetem Wert."""
    outcome_list = outcomes if outcomes is not None else ["ok"] * len(weights)
    return [
        runs.build_record(task=task, variant=variant, run=i, project=Path("/p"),
                          outcome=outcome_list[i - 1], note="", measured=_measured(w),
                          env={"round": "2026-05-02", "model": "claude-opus-5",
                               "cli_version": "2.0.0", "prompt_sha": "aaa"})
        for i, w in enumerate(weights, 1)
    ]


def judged(*groups: list[dict], baseline: str = "basis") -> dict[str, dict]:
    """Die Tabelle zu mehreren Varianten - der Weg, den auch `bench.py compare` geht."""
    return verdict.judge([r for g in groups for r in g], {"t1": baseline}).table


class Urteil(unittest.TestCase):
    def test_basis_gegen_sich_selbst(self):
        t = judged(runs_of("basis", 100, 150, 200))
        self.assertEqual(t[Key("t1", "basis")]["verdict"], {"kind": "baseline"})

    def test_keine_daten_bei_fehlendem_median(self):
        t = judged(runs_of("basis", 100, 150, 200), runs_of("neu", None))
        self.assertEqual(t[Key("t1", "neu")]["verdict"]["kind"], "no-data")

    def test_median_null_ist_kein_fehlender_wert(self):
        t = judged(runs_of("basis", 0, 0, 0), runs_of("neu", 400, 500, 600))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertNotEqual(v["kind"], "no-data")
        self.assertEqual(v["kind"], "costlier")
        self.assertIsNone(v["delta"])
        self.assertEqual(report.render_verdict(v), "teurer (Basis-Median 0)")

    def test_n_gleich_zwei_gegen_drei_urteilt_mit_vorbehalt(self):
        t = judged(runs_of("basis", 100, 150, 200), runs_of("neu", 380, 420))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertEqual(v["kind"], "costlier")
        self.assertTrue(v["thin"])
        self.assertEqual((v["n_baseline"], v["n_variant"]), (3, 2))
        self.assertIn("ungesichert", report.render_verdict(v))

    def test_einzellauf_urteilt_und_kennzeichnet(self):
        t = judged(runs_of("basis", 1000), runs_of("neu", 500))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertEqual(v["kind"], "cheaper")
        self.assertEqual(v["delta"], -0.5)
        self.assertEqual(report.render_verdict(v), "guenstiger um 50 % (n=1 - ungesichert)")

    def test_drei_laeufe_bleiben_ohne_vorbehalt(self):
        t = judged(runs_of("basis", 900, 1000, 1100), runs_of("neu", 400, 500, 600))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertFalse(v["thin"])
        self.assertEqual(report.render_verdict(v), "guenstiger um 50 %")

    def test_einzelner_unset_lauf_macht_ertrag_offen(self):
        t = judged(runs_of("basis", 100, 150, 200),
                   runs_of("neu", 380, 400, 420, outcomes=["ok", "ok", "unset"]))
        self.assertEqual(t[Key("t1", "neu")]["verdict"]["kind"], "outcome-open")

    def test_fail_lauf_macht_ertrag_offen(self):
        t = judged(runs_of("basis", 100, 150, 200),
                   runs_of("neu", 380, 400, 420, outcomes=["ok", "ok", "fail"]))
        self.assertEqual(t[Key("t1", "neu")]["verdict"]["kind"], "outcome-open")

    def test_spannen_ueberlappen_um_genau_ein_token(self):
        # 200 liegt in beiden Spannen
        t = judged(runs_of("basis", 100, 150, 200), runs_of("neu", 200, 250, 300))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertEqual(v["kind"], "no-difference")
        self.assertEqual(report.render_verdict(v),
                         "kein belastbarer Unterschied (Spannen ueberlappen)")

    def test_spannen_exakt_buendig_ohne_ueberlappung(self):
        # direkt anschliessend, kein gemeinsamer Wert
        t = judged(runs_of("basis", 100, 150, 200), runs_of("neu", 201, 250, 300))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertEqual(v["kind"], "costlier")
        self.assertAlmostEqual(v["delta"], (250 - 150) / 150, places=4)

    def test_guenstiger_bei_niedrigerem_median(self):
        t = judged(runs_of("basis", 380, 400, 420), runs_of("neu", 180, 200, 220))
        v = t[Key("t1", "neu")]["verdict"]
        self.assertEqual(v["kind"], "cheaper")
        self.assertLess(v["delta"], 0)
        self.assertTrue(report.render_verdict(v).startswith("guenstiger um "))

    def test_jede_variante_bekommt_ihr_urteil(self):
        t = judged(runs_of("basis", 100, 150, 200), runs_of("neu", 201, 250, 300))
        self.assertEqual(t[Key("t1", "basis")]["verdict"]["kind"], "baseline")
        self.assertEqual(t[Key("t1", "neu")]["verdict"]["kind"], "costlier")


class Bericht(unittest.TestCase):
    def test_report_rendert_median_null_als_zahl_nicht_als_strich(self):
        t = judged(runs_of("basis", 0, 0, 0), runs_of("neu", 400, 500, 600))
        text = report.render_table(t, baseline={"t1": "basis"})
        self.assertIn("| basis | 3 | 0 |", text)
        self.assertIn("Basis |", text)

    def test_report_markdown_zeichengleich_ausserhalb_median_null(self):
        t = judged(runs_of("basis", 100, 150, 200), runs_of("neu", 201, 250, 300))
        text = report.render_table(t, baseline={"t1": "basis"})
        self.assertIn("| basis | 3 | 150 | 100-200 | - | - | 0 % | ok:3 | Basis |", text)
        self.assertIn("teurer um 67 %", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
