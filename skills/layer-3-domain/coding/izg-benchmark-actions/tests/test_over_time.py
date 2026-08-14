#!/usr/bin/env python3
"""Tests fuer die Messung ueber die Zeit - stdlib only (kein pytest noetig).

Geprueft wird die Regel, die eine Optimierungsmessung ueberhaupt belastbar macht: dass
Zahlen aus zwei Messrunden, von zwei Modellen oder zu zwei Fassungen der Testaufgabe
*kein* Urteil ergeben, sondern eine Aufforderung, neu zu messen. Dazu der Messplan, der
eine Messung Monate spaeter wiederholbar haelt, und der Verlauf ueber die Runden.

Kein Dateisystem ausser tmp_path, kein claude-Aufruf.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_over_time.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bench  # noqa: E402
import plans  # noqa: E402
import runs  # noqa: E402


def mk(variant: str, n: int = 3, median: int = 100, wmin: int = 90, wmax: int = 110,
       *, task: str = "t1", rounds: list[str] | None = None, models: list[str] | None = None,
       shas: list[str] | None = None, rnd: str | None = None) -> dict:
    return {
        "task": task, "variant": variant, "round": rnd, "n": n,
        "weighted_median": median, "weighted_min": wmin, "weighted_max": wmax,
        "cost_median": None, "turns_median": None, "cache_hit_median": 0.0,
        "outcomes": {"ok": n},
        "rounds": rounds if rounds is not None else ["2026-05-02"],
        "models": models if models is not None else ["claude-opus-5"],
        "cli_versions": ["2.0.0"],
        "prompt_shas": shas if shas is not None else ["aaa"],
        "last_recorded": "2026-05-02T10:00:00+00:00",
    }


def measured(w: int) -> dict:
    return {"session_id": f"s{w}", "requests": 1, "usage": {"input": w}, "weighted_tokens": w,
            "raw_tokens": w, "cache_hit_rate": 0.0, "tool_calls": {}, "tool_result_tokens": {},
            "skills_used": {}, "subagent_output_tokens": 0,
            "first_timestamp": "t0", "last_timestamp": "t1"}


class Vergleichbarkeit(unittest.TestCase):
    def test_zwei_messrunden_ergeben_kein_urteil(self):
        base = mk("v1", median=500, wmin=480, wmax=520, rounds=["2026-05-02"])
        neu = mk("v2", median=100, wmin=90, wmax=110, rounds=["2026-08-14"])
        v = bench.verdict(base, neu)
        self.assertEqual(v["art"], "runden-gemischt")
        self.assertEqual(v["runden"], ["2026-05-02", "2026-08-14"])
        self.assertIn("neu messen", bench.render_verdict(v))

    def test_across_rounds_hebt_die_rundensperre_auf(self):
        base = mk("v1", median=500, wmin=480, wmax=520, rounds=["2026-05-02"])
        neu = mk("v2", median=100, wmin=90, wmax=110, rounds=["2026-08-14"])
        v = bench.verdict(base, neu, strict_round=False)
        self.assertEqual(v["art"], "guenstiger")

    def test_verschiedene_modelle_ergeben_kein_urteil(self):
        base = mk("v1", median=500, wmin=480, wmax=520, models=["claude-opus-4-5"])
        neu = mk("v2", median=100, wmin=90, wmax=110, models=["claude-opus-5"])
        # Auch ohne Rundensperre bleibt das Modell ein Ausschlussgrund.
        v = bench.verdict(base, neu, strict_round=False)
        self.assertEqual(v["art"], "modell-gemischt")
        self.assertIn("nicht vergleichbar", bench.render_verdict(v))

    def test_geaenderte_testaufgabe_schlaegt_alles_andere(self):
        base = mk("v1", median=500, wmin=480, wmax=520, shas=["aaa"])
        neu = mk("v2", median=100, wmin=90, wmax=110, shas=["bbb"], models=["anderes"])
        self.assertEqual(bench.verdict(base, neu)["art"], "aufgabe-geaendert")

    def test_eine_variante_aus_zwei_modellen_ist_selbst_schon_unvergleichbar(self):
        base = mk("v1", median=500, wmin=480, wmax=520)
        neu = mk("v2", median=100, wmin=90, wmax=110,
                 models=["claude-opus-4-5", "claude-opus-5"])
        self.assertEqual(bench.verdict(base, neu)["art"], "modell-gemischt")

    def test_unbekannte_umgebung_blockiert_nicht(self):
        # Altdaten ohne Umgebungsfelder: None ist "unbekannt", nicht "abweichend".
        base = mk("v1", median=500, wmin=480, wmax=520, rounds=[], models=[], shas=[])
        neu = mk("v2", median=100, wmin=90, wmax=110, rounds=[], models=[], shas=[])
        self.assertEqual(bench.verdict(base, neu)["art"], "guenstiger")

    def test_gleiche_runde_und_modell_urteilt_normal(self):
        base = mk("v1", median=500, wmin=480, wmax=520)
        neu = mk("v2", median=100, wmin=90, wmax=110)
        self.assertEqual(bench.verdict(base, neu)["art"], "guenstiger")


class RundenGruppierung(unittest.TestCase):
    def test_attach_verdicts_vergleicht_nur_innerhalb_einer_runde(self):
        summary = {
            "t1::r1::v1": mk("v1", median=500, wmin=480, wmax=520, rnd="r1", rounds=["r1"]),
            "t1::r1::v2": mk("v2", median=100, wmin=90, wmax=110, rnd="r1", rounds=["r1"]),
            "t1::r2::v2": mk("v2", median=120, wmin=110, wmax=130, rnd="r2", rounds=["r2"]),
            "t1::r2::v3": mk("v3", median=60, wmin=50, wmax=70, rnd="r2", rounds=["r2"]),
        }
        bench.attach_verdicts(summary, baseline="v2")
        # v2 ist in beiden Runden Basis, v1 und v3 werden je gegen ihre eigene Runde geurteilt.
        self.assertEqual(summary["t1::r1::v2"]["urteil"]["art"], "basis")
        self.assertEqual(summary["t1::r2::v2"]["urteil"]["art"], "basis")
        self.assertEqual(summary["t1::r1::v1"]["urteil"]["art"], "teurer")
        self.assertEqual(summary["t1::r2::v3"]["urteil"]["art"], "guenstiger")

    def test_summarize_trennt_runden_nur_auf_verlangen(self):
        recs = []
        for i, (w, rnd) in enumerate([(100, "r1"), (110, "r1"), (200, "r2"), (210, "r2")], 1):
            recs.append(runs.build_record(
                task="t1", variant="v1", run=i, project=Path("/p"), outcome="ok", note="",
                measured=measured(w), env={"round": rnd, "model": "m", "cli_version": "c",
                                           "prompt_sha": "aaa"}))
        flach = bench.summarize(recs)
        self.assertEqual(flach["t1::v1"]["n"], 4)
        self.assertEqual(flach["t1::v1"]["rounds"], ["r1", "r2"])

        proRunde = bench.summarize(recs, group_round=True)
        self.assertEqual(set(proRunde), {"t1::r1::v1", "t1::r2::v1"})
        self.assertEqual(proRunde["t1::r1::v1"]["weighted_median"], 105)
        self.assertEqual(proRunde["t1::r2::v1"]["weighted_median"], 205)

    def test_laeufe_ohne_runde_landen_in_einem_eigenen_topf(self):
        rec = runs.build_record(task="t1", variant="v1", run=1, project=Path("/p"),
                                 outcome="ok", note="", measured=measured(100))
        s = bench.summarize([rec], group_round=True)
        self.assertEqual(list(s), ["t1::ohne-runde::v1"])
        self.assertEqual(s["t1::ohne-runde::v1"]["rounds"], [])


class Verlauf(unittest.TestCase):
    def test_trend_zeigt_delta_und_umgebungswechsel(self):
        summary = {
            "t1::r1::v2": mk("v2", rnd="2026-05-02", median=40000, models=["opus-4-5"]),
            "t1::r2::v2": mk("v2", rnd="2026-08-14", median=44000, models=["opus-5"]),
        }
        t = bench.trend(summary)["t1::v2"]
        self.assertEqual([p["round"] for p in t], ["2026-05-02", "2026-08-14"])
        self.assertIsNone(t[0]["delta_zur_vorrunde"])
        self.assertAlmostEqual(t[1]["delta_zur_vorrunde"], 0.1, places=4)
        self.assertTrue(t[1]["umgebung_gewechselt"])
        self.assertIn("Modell/CLI gewechselt", bench.render_trend({"t1::v2": t}))

    def test_eine_einzelne_runde_ergibt_keinen_verlauf(self):
        summary = {"t1::r1::v2": mk("v2", rnd="2026-05-02")}
        self.assertEqual(bench.trend(summary), {})
        self.assertIn("Nur eine Messrunde", bench.render_trend({}))


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
            runs.write_record(out, runs.build_record(
                task="t1", variant="v1", run=1, project=Path("/p"), outcome="ok",
                note="", measured=measured(100)))
            plans.save_plan(out, plans.new_plan("t1"))
            self.assertEqual(len(runs.load_records(out, "t1")), 1)


class Altdaten(unittest.TestCase):
    def test_laufdaten_ohne_umgebungsfelder_bleiben_lesbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rec = runs.build_record(task="t1", variant="v1", run=1, project=Path("/p"),
                                     outcome="ok", note="", measured=measured(100))
            for f in ("round", "model", "cli_version", "prompt_sha"):
                del rec[f]
            (out / "t1__v1__01.json").parent.mkdir(parents=True, exist_ok=True)
            import json
            (out / "t1__v1__01.json").write_text(json.dumps(rec), encoding="utf-8")
            geladen = runs.load_records(out, "t1")
            self.assertEqual(len(geladen), 1)
            self.assertIsNone(geladen[0]["round"])
            # und sie fallen durch summarize, ohne dass ein Feld fehlt
            self.assertEqual(bench.summarize(geladen)["t1::v1"]["models"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
