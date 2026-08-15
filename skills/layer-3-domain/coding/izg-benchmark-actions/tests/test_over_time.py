#!/usr/bin/env python3
"""Tests fuer die Messung ueber die Zeit - stdlib only (kein pytest noetig).

Geprueft wird die Regel, die eine Optimierungsmessung ueberhaupt belastbar macht: dass
Zahlen aus zwei Messrunden, von zwei Modellen oder zu zwei Fassungen der Testaufgabe
*kein* Urteil ergeben, sondern eine Aufforderung, neu zu messen. Dazu der Messplan, der
eine Messung Monate spaeter wiederholbar haelt, und der Verlauf ueber die Runden.

Alles ueber `urteil.beurteile()`: Laufdaten und Basis herein, beurteilte Tabelle heraus -
derselbe Weg, den `bench.py compare` und `bench.py history` gehen. Kein Dateisystem ausser
tmp_path, kein claude-Aufruf.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_over_time.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bericht  # noqa: E402
import plans  # noqa: E402
import runs  # noqa: E402
import urteil  # noqa: E402


def measured(w: int) -> dict:
    return {"session_id": f"s{w}", "requests": 1, "usage": {"input": w}, "weighted_tokens": w,
            "raw_tokens": w, "cache_hit_rate": 0.0, "tool_calls": {}, "tool_result_tokens": {},
            "skills_used": {}, "subagent_output_tokens": 0,
            "first_timestamp": "t0", "last_timestamp": "t1"}


def laeufe(variant: str, *gewichte: int, task: str = "t1", rnd: str | None = "2026-05-02",
           models: list[str] | None = None, sha: str | None = "aaa",
           cli: str | None = "2.0.0") -> list[dict]:
    """Laufdatensaetze einer Variante - ein Datensatz je gewichtetem Wert.

    `models` darf mehrere Modelle tragen: eine Variante, die aus zwei Modellen
    zusammengesetzt ist, muss selbst schon unvergleichbar sein.
    """
    mods = models if models is not None else ["claude-opus-5"]
    return [
        runs.build_record(task=task, variant=variant, run=i, project=Path("/p"),
                          outcome="ok", note="", measured=measured(w),
                          env={"round": rnd, "model": mods[(i - 1) % len(mods)],
                               "cli_version": cli, "prompt_sha": sha})
        for i, w in enumerate(gewichte, 1)
    ]


def beurteile(*gruppen: list[dict], baseline: str = "v1", **kw) -> urteil.Beurteilung:
    return urteil.beurteile([r for g in gruppen for r in g], baseline, **kw)


class Vergleichbarkeit(unittest.TestCase):
    def test_zwei_messrunden_ergeben_kein_urteil(self):
        t = beurteile(laeufe("v1", 480, 500, 520, rnd="2026-05-02"),
                      laeufe("v2", 90, 100, 110, rnd="2026-08-14")).tabelle
        v = t["t1::v2"]["urteil"]
        self.assertEqual(v["art"], "runden-gemischt")
        self.assertEqual(v["runden"], ["2026-05-02", "2026-08-14"])
        self.assertIn("neu messen", bericht.render_verdict(v))

    def test_across_rounds_hebt_die_rundensperre_auf(self):
        t = beurteile(laeufe("v1", 480, 500, 520, rnd="2026-05-02"),
                      laeufe("v2", 90, 100, 110, rnd="2026-08-14"),
                      strict_round=False).tabelle
        self.assertEqual(t["t1::v2"]["urteil"]["art"], "guenstiger")

    def test_verschiedene_modelle_ergeben_kein_urteil(self):
        # Auch ohne Rundensperre bleibt das Modell ein Ausschlussgrund.
        t = beurteile(laeufe("v1", 480, 500, 520, models=["claude-opus-4-5"]),
                      laeufe("v2", 90, 100, 110, models=["claude-opus-5"]),
                      strict_round=False).tabelle
        v = t["t1::v2"]["urteil"]
        self.assertEqual(v["art"], "modell-gemischt")
        self.assertIn("nicht vergleichbar", bericht.render_verdict(v))

    def test_geaenderte_testaufgabe_schlaegt_alles_andere(self):
        t = beurteile(laeufe("v1", 480, 500, 520, sha="aaa"),
                      laeufe("v2", 90, 100, 110, sha="bbb", models=["anderes"])).tabelle
        self.assertEqual(t["t1::v2"]["urteil"]["art"], "aufgabe-geaendert")

    def test_eine_variante_aus_zwei_modellen_ist_selbst_schon_unvergleichbar(self):
        t = beurteile(laeufe("v1", 480, 500, 520),
                      laeufe("v2", 90, 100, 110,
                             models=["claude-opus-4-5", "claude-opus-5"])).tabelle
        self.assertEqual(t["t1::v2"]["urteil"]["art"], "modell-gemischt")

    def test_unbekannte_umgebung_blockiert_nicht(self):
        # Altdaten ohne Umgebungsfelder: None ist "unbekannt", nicht "abweichend".
        leer = {"rnd": None, "models": [None], "sha": None, "cli": None}
        t = beurteile(laeufe("v1", 480, 500, 520, **leer),
                      laeufe("v2", 90, 100, 110, **leer)).tabelle
        self.assertEqual(t["t1::v2"]["urteil"]["art"], "guenstiger")

    def test_gleiche_runde_und_modell_urteilt_normal(self):
        t = beurteile(laeufe("v1", 480, 500, 520), laeufe("v2", 90, 100, 110)).tabelle
        self.assertEqual(t["t1::v2"]["urteil"]["art"], "guenstiger")


class RundenGruppierung(unittest.TestCase):
    def test_urteil_faellt_nur_innerhalb_einer_runde(self):
        t = beurteile(laeufe("v1", 480, 500, 520, rnd="r1"),
                      laeufe("v2", 90, 100, 110, rnd="r1"),
                      laeufe("v2", 110, 120, 130, rnd="r2"),
                      laeufe("v3", 50, 60, 70, rnd="r2"),
                      baseline="v2", je_runde=True).tabelle
        # v2 ist in beiden Runden Basis, v1 und v3 werden je gegen ihre eigene Runde geurteilt.
        self.assertEqual(t["t1::r1::v2"]["urteil"]["art"], "basis")
        self.assertEqual(t["t1::r2::v2"]["urteil"]["art"], "basis")
        self.assertEqual(t["t1::r1::v1"]["urteil"]["art"], "teurer")
        self.assertEqual(t["t1::r2::v3"]["urteil"]["art"], "guenstiger")

    def test_runden_werden_nur_auf_verlangen_getrennt(self):
        recs = laeufe("v1", 100, 110, rnd="r1") + laeufe("v1", 200, 210, rnd="r2")
        flach = urteil.beurteile(recs, "v1").tabelle
        self.assertEqual(flach["t1::v1"]["n"], 4)
        self.assertEqual(flach["t1::v1"]["rounds"], ["r1", "r2"])

        proRunde = urteil.beurteile(recs, "v1", je_runde=True).tabelle
        self.assertEqual(set(proRunde), {"t1::r1::v1", "t1::r2::v1"})
        self.assertEqual(proRunde["t1::r1::v1"]["weighted_median"], 105)
        self.assertEqual(proRunde["t1::r2::v1"]["weighted_median"], 205)

    def test_laeufe_ohne_runde_landen_in_einem_eigenen_topf(self):
        t = urteil.beurteile(laeufe("v1", 100, rnd=None), "v1", je_runde=True).tabelle
        self.assertEqual(list(t), ["t1::ohne-runde::v1"])
        self.assertEqual(t["t1::ohne-runde::v1"]["rounds"], [])


class Verlauf(unittest.TestCase):
    def test_verlauf_zeigt_delta_und_umgebungswechsel(self):
        b = beurteile(laeufe("v2", 40000, rnd="2026-05-02", models=["opus-4-5"]),
                      laeufe("v2", 44000, rnd="2026-08-14", models=["opus-5"]),
                      baseline="v2", je_runde=True)
        reihe = b.verlauf["t1::v2"]
        self.assertEqual([p["round"] for p in reihe], ["2026-05-02", "2026-08-14"])
        self.assertIsNone(reihe[0]["delta_zur_vorrunde"])
        self.assertAlmostEqual(reihe[1]["delta_zur_vorrunde"], 0.1, places=4)
        self.assertTrue(reihe[1]["umgebung_gewechselt"])
        self.assertIn("Modell/CLI gewechselt", bericht.render_trend(b.verlauf))

    def test_eine_einzelne_runde_ergibt_keinen_verlauf(self):
        b = beurteile(laeufe("v2", 40000, rnd="2026-05-02"), baseline="v2", je_runde=True)
        self.assertEqual(b.verlauf, {})
        self.assertIn("Nur eine Messrunde", bericht.render_trend(b.verlauf))

    def test_ohne_rundentrennung_gibt_es_keinen_verlauf(self):
        b = beurteile(laeufe("v2", 40000, rnd="2026-05-02"),
                      laeufe("v2", 44000, rnd="2026-08-14"), baseline="v2")
        self.assertEqual(b.verlauf, {})


class Messplan(unittest.TestCase):
    def test_plan_fuellt_nur_fehlende_werte_und_meldet_abweichungen(self):
        plan = plans.new_plan("t1")
        plan.update({"project": "/a", "model": "opus-5", "prompt_file": "/a/aufgabe.md"})
        gefuellt, notes = plans.fill_from_plan(
            plan, {"project": None, "model": "opus-4-5", "prompt_file": None,
                   "permission_mode": None, "timeout": None})
        self.assertEqual(gefuellt["project"], "/a")          # fehlte -> aus dem Plan
        self.assertEqual(gefuellt["model"], "opus-4-5")      # gesetzt -> Aufruf gewinnt
        self.assertEqual(len(notes), 1)
        self.assertIn("model", notes[0])

    def test_plan_ueberlebt_speichern_und_laden(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            plan = plans.new_plan("t1")
            plans.record_variant(plan, "v2", "git checkout v2 -- .claude/")
            plans.save_plan(out, plan)
            wieder = plans.load_plan(out, "t1")
            self.assertEqual(plans.variant_setup(wieder, "v2"), "git checkout v2 -- .claude/")
            self.assertIsNotNone(wieder["updated_at"])

    def test_neue_variante_wird_ergaenzt_geaenderte_umschaltung_gemeldet(self):
        plan = plans.new_plan("t1")
        self.assertIn("ergaenzt", plans.record_variant(plan, "v2", "cmd-a"))
        self.assertIsNone(plans.record_variant(plan, "v2", "cmd-a"))
        self.assertIn("aktualisiert", plans.record_variant(plan, "v2", "cmd-b"))
        self.assertEqual(plans.variant_setup(plan, "v2"), "cmd-b")

    def test_geaenderte_testaufgabe_aendert_die_pruefsumme(self):
        self.assertNotEqual(plans.prompt_sha("Leg ein Ticket an."),
                            plans.prompt_sha("Leg ein Ticket an!"))

    def test_messplan_liegt_neben_den_laufdaten_nicht_zwischen_ihnen(self):
        # load_records() darf den Plan nicht als Lauf einlesen.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            runs.write_record(out, laeufe("v1", 100)[0])
            plans.save_plan(out, plans.new_plan("t1"))
            self.assertEqual(len(runs.load_records(out, "t1")), 1)


class Altdaten(unittest.TestCase):
    def test_laufdaten_ohne_umgebungsfelder_bleiben_lesbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rec = laeufe("v1", 100)[0]
            for f in ("round", "model", "cli_version", "prompt_sha"):
                del rec[f]
            import json
            (out / "t1__v1__01.json").write_text(json.dumps(rec), encoding="utf-8")
            geladen = runs.load_records(out, "t1")
            self.assertEqual(len(geladen), 1)
            self.assertIsNone(geladen[0]["round"])
            # und sie fallen durch die Auswertung, ohne dass ein Feld fehlt
            self.assertEqual(urteil.beurteile(geladen, "v1").tabelle["t1::v1"]["models"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
