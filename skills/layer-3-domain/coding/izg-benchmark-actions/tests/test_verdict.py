#!/usr/bin/env python3
"""Tests fuer das Urteil und seine Darstellung - stdlib only (kein pytest noetig).

Kein Dateisystem, kein HOME-Zugriff, kein claude-Aufruf: die Laufdatensaetze werden von
Hand gebaut statt ueber load_records()/measure_session() erzeugt, und alles laeuft durch
den einen Einstieg `urteil.beurteile()` - Laufdaten und Basis herein, beurteilte Tabelle
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

import bericht  # noqa: E402
import runs  # noqa: E402
import urteil  # noqa: E402


def _measured(w: int | None) -> dict:
    return {"session_id": f"s{w}", "requests": 1, "usage": {"input": w or 0},
            "weighted_tokens": w, "raw_tokens": w or 0, "cache_hit_rate": 0.0,
            "tool_calls": {}, "tool_result_tokens": {}, "skills_used": {},
            "subagent_output_tokens": 0, "first_timestamp": "t0", "last_timestamp": "t1"}


def laeufe(variant: str, *gewichte: int | None, task: str = "t1",
           outcomes: list[str] | None = None) -> list[dict]:
    """Laufdatensaetze einer Variante - ein Datensatz je gewichtetem Wert."""
    ertraege = outcomes if outcomes is not None else ["ok"] * len(gewichte)
    return [
        runs.build_record(task=task, variant=variant, run=i, project=Path("/p"),
                          outcome=ertraege[i - 1], note="", measured=_measured(w),
                          env={"round": "2026-05-02", "model": "claude-opus-5",
                               "cli_version": "2.0.0", "prompt_sha": "aaa"})
        for i, w in enumerate(gewichte, 1)
    ]


def beurteile(*gruppen: list[dict], baseline: str = "basis") -> dict[str, dict]:
    """Die Tabelle zu mehreren Varianten - der Weg, den auch `bench.py compare` geht."""
    return urteil.beurteile([r for g in gruppen for r in g], baseline).tabelle


class Urteil(unittest.TestCase):
    def test_basis_gegen_sich_selbst(self):
        t = beurteile(laeufe("basis", 100, 150, 200))
        self.assertEqual(t["t1::basis"]["urteil"], {"art": "basis"})

    def test_keine_daten_bei_fehlendem_median(self):
        t = beurteile(laeufe("basis", 100, 150, 200), laeufe("neu", None))
        self.assertEqual(t["t1::neu"]["urteil"]["art"], "keine-daten")

    def test_median_null_ist_kein_fehlender_wert(self):
        t = beurteile(laeufe("basis", 0, 0, 0), laeufe("neu", 400, 500, 600))
        v = t["t1::neu"]["urteil"]
        self.assertNotEqual(v["art"], "keine-daten")
        self.assertEqual(v["art"], "teurer")
        self.assertIsNone(v["delta"])
        self.assertEqual(bericht.render_verdict(v), "teurer (Basis-Median 0)")

    def test_n_gleich_zwei_gegen_drei_urteilt_mit_vorbehalt(self):
        t = beurteile(laeufe("basis", 100, 150, 200), laeufe("neu", 380, 420))
        v = t["t1::neu"]["urteil"]
        self.assertEqual(v["art"], "teurer")
        self.assertTrue(v["duenn"])
        self.assertEqual((v["n_basis"], v["n_variante"]), (3, 2))
        self.assertIn("ungesichert", bericht.render_verdict(v))

    def test_einzellauf_urteilt_und_kennzeichnet(self):
        t = beurteile(laeufe("basis", 1000), laeufe("neu", 500))
        v = t["t1::neu"]["urteil"]
        self.assertEqual(v["art"], "guenstiger")
        self.assertEqual(v["delta"], -0.5)
        self.assertEqual(bericht.render_verdict(v), "guenstiger um 50 % (n=1 - ungesichert)")

    def test_drei_laeufe_bleiben_ohne_vorbehalt(self):
        t = beurteile(laeufe("basis", 900, 1000, 1100), laeufe("neu", 400, 500, 600))
        v = t["t1::neu"]["urteil"]
        self.assertFalse(v["duenn"])
        self.assertEqual(bericht.render_verdict(v), "guenstiger um 50 %")

    def test_einzelner_unset_lauf_macht_ertrag_offen(self):
        t = beurteile(laeufe("basis", 100, 150, 200),
                      laeufe("neu", 380, 400, 420, outcomes=["ok", "ok", "unset"]))
        self.assertEqual(t["t1::neu"]["urteil"]["art"], "ertrag-offen")

    def test_fail_lauf_macht_ertrag_offen(self):
        t = beurteile(laeufe("basis", 100, 150, 200),
                      laeufe("neu", 380, 400, 420, outcomes=["ok", "ok", "fail"]))
        self.assertEqual(t["t1::neu"]["urteil"]["art"], "ertrag-offen")

    def test_spannen_ueberlappen_um_genau_ein_token(self):
        # 200 liegt in beiden Spannen
        t = beurteile(laeufe("basis", 100, 150, 200), laeufe("neu", 200, 250, 300))
        v = t["t1::neu"]["urteil"]
        self.assertEqual(v["art"], "kein-unterschied")
        self.assertEqual(bericht.render_verdict(v),
                         "kein belastbarer Unterschied (Spannen ueberlappen)")

    def test_spannen_exakt_buendig_ohne_ueberlappung(self):
        # direkt anschliessend, kein gemeinsamer Wert
        t = beurteile(laeufe("basis", 100, 150, 200), laeufe("neu", 201, 250, 300))
        v = t["t1::neu"]["urteil"]
        self.assertEqual(v["art"], "teurer")
        self.assertAlmostEqual(v["delta"], (250 - 150) / 150, places=4)

    def test_guenstiger_bei_niedrigerem_median(self):
        t = beurteile(laeufe("basis", 380, 400, 420), laeufe("neu", 180, 200, 220))
        v = t["t1::neu"]["urteil"]
        self.assertEqual(v["art"], "guenstiger")
        self.assertLess(v["delta"], 0)
        self.assertTrue(bericht.render_verdict(v).startswith("guenstiger um "))

    def test_jede_variante_bekommt_ihr_urteil(self):
        t = beurteile(laeufe("basis", 100, 150, 200), laeufe("neu", 201, 250, 300))
        self.assertEqual(t["t1::basis"]["urteil"]["art"], "basis")
        self.assertEqual(t["t1::neu"]["urteil"]["art"], "teurer")


class Bericht(unittest.TestCase):
    def test_report_rendert_median_null_als_zahl_nicht_als_strich(self):
        t = beurteile(laeufe("basis", 0, 0, 0), laeufe("neu", 400, 500, 600))
        text = bericht.report(t, baseline="basis")
        self.assertIn("| basis | 3 | 0 |", text)
        self.assertIn("Basis |", text)

    def test_report_markdown_zeichengleich_ausserhalb_median_null(self):
        t = beurteile(laeufe("basis", 100, 150, 200), laeufe("neu", 201, 250, 300))
        text = bericht.report(t, baseline="basis")
        self.assertIn("| basis | 3 | 150 | 100-200 | - | - | 0 % | ok:3 | Basis |", text)
        self.assertIn("teurer um 67 %", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
