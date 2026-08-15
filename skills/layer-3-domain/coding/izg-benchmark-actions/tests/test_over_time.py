#!/usr/bin/env python3
"""Tests fuer die Messung ueber die Zeit - stdlib only (kein pytest noetig).

Geprueft wird die Regel, die eine Optimierungsmessung ueberhaupt belastbar macht: dass
Zahlen aus zwei Messrunden, von zwei Modellen oder zu zwei Fassungen der Testaufgabe
*kein* Urteil ergeben, sondern eine Aufforderung, neu zu messen. Dazu der Messplan, der
eine Messung Monate spaeter wiederholbar haelt, und der Verlauf ueber die Runden.

Alles ueber `verdict.judge()`: Laufdaten und Basis herein, beurteilte Tabelle heraus -
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

import plans  # noqa: E402
import report  # noqa: E402
import runs  # noqa: E402
import verdict  # noqa: E402
from verdict import Key  # noqa: E402


def measured(w: int) -> dict:
    return {"session_id": f"s{w}", "requests": 1, "usage": {"input": w}, "weighted_tokens": w,
            "raw_tokens": w, "cache_hit_rate": 0.0, "tool_calls": {}, "tool_result_tokens": {},
            "skills_used": {}, "subagent_output_tokens": 0,
            "first_timestamp": "t0", "last_timestamp": "t1"}


def runs_of(variant: str, *weights: int, task: str = "t1", rnd: str | None = "2026-05-02",
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
        for i, w in enumerate(weights, 1)
    ]


def judged(*groups: list[dict], baseline: str = "v1", **kw) -> verdict.Judgement:
    return verdict.judge([r for g in groups for r in g], {"t1": baseline}, **kw)


class Vergleichbarkeit(unittest.TestCase):
    def test_zwei_messrunden_ergeben_kein_urteil(self):
        t = judged(runs_of("v1", 480, 500, 520, rnd="2026-05-02"),
                   runs_of("v2", 90, 100, 110, rnd="2026-08-14")).table
        v = t[Key("t1", "v2")]["verdict"]
        self.assertEqual(v["kind"], "rounds-mixed")
        self.assertEqual(v["rounds"], ["2026-05-02", "2026-08-14"])
        self.assertIn("neu messen", report.render_verdict(v))

    def test_across_rounds_hebt_die_rundensperre_auf(self):
        t = judged(runs_of("v1", 480, 500, 520, rnd="2026-05-02"),
                   runs_of("v2", 90, 100, 110, rnd="2026-08-14"),
                   strict_round=False).table
        self.assertEqual(t[Key("t1", "v2")]["verdict"]["kind"], "cheaper")

    def test_verschiedene_modelle_ergeben_kein_urteil(self):
        # Auch ohne Rundensperre bleibt das Modell ein Ausschlussgrund.
        t = judged(runs_of("v1", 480, 500, 520, models=["claude-opus-4-5"]),
                   runs_of("v2", 90, 100, 110, models=["claude-opus-5"]),
                   strict_round=False).table
        v = t[Key("t1", "v2")]["verdict"]
        self.assertEqual(v["kind"], "model-mixed")
        self.assertIn("nicht vergleichbar", report.render_verdict(v))

    def test_geaenderte_testaufgabe_schlaegt_alles_andere(self):
        t = judged(runs_of("v1", 480, 500, 520, sha="aaa"),
                   runs_of("v2", 90, 100, 110, sha="bbb", models=["anderes"])).table
        self.assertEqual(t[Key("t1", "v2")]["verdict"]["kind"], "task-changed")

    def test_eine_variante_aus_zwei_modellen_ist_selbst_schon_unvergleichbar(self):
        t = judged(runs_of("v1", 480, 500, 520),
                   runs_of("v2", 90, 100, 110,
                          models=["claude-opus-4-5", "claude-opus-5"])).table
        self.assertEqual(t[Key("t1", "v2")]["verdict"]["kind"], "model-mixed")

    def test_unbekannte_umgebung_blockiert_nicht(self):
        # Altdaten ohne Umgebungsfelder: None ist "unbekannt", nicht "abweichend".
        empty = {"rnd": None, "models": [None], "sha": None, "cli": None}
        t = judged(runs_of("v1", 480, 500, 520, **empty),
                   runs_of("v2", 90, 100, 110, **empty)).table
        self.assertEqual(t[Key("t1", "v2")]["verdict"]["kind"], "cheaper")

    def test_gleiche_runde_und_modell_urteilt_normal(self):
        t = judged(runs_of("v1", 480, 500, 520), runs_of("v2", 90, 100, 110)).table
        self.assertEqual(t[Key("t1", "v2")]["verdict"]["kind"], "cheaper")


class RundenGruppierung(unittest.TestCase):
    def test_urteil_faellt_nur_innerhalb_einer_runde(self):
        t = judged(runs_of("v1", 480, 500, 520, rnd="r1"),
                   runs_of("v2", 90, 100, 110, rnd="r1"),
                   runs_of("v2", 110, 120, 130, rnd="r2"),
                   runs_of("v3", 50, 60, 70, rnd="r2"),
                   baseline="v2", per_round=True).table
        # v2 ist in beiden Runden Basis, v1 und v3 werden je gegen ihre eigene Runde geurteilt.
        self.assertEqual(t[Key("t1", "v2", "r1")]["verdict"]["kind"], "baseline")
        self.assertEqual(t[Key("t1", "v2", "r2")]["verdict"]["kind"], "baseline")
        self.assertEqual(t[Key("t1", "v1", "r1")]["verdict"]["kind"], "costlier")
        self.assertEqual(t[Key("t1", "v3", "r2")]["verdict"]["kind"], "cheaper")

    def test_runden_werden_nur_auf_verlangen_getrennt(self):
        recs = runs_of("v1", 100, 110, rnd="r1") + runs_of("v1", 200, 210, rnd="r2")
        flach = verdict.judge(recs, {"t1": "v1"}).table
        self.assertEqual(flach[Key("t1", "v1")]["n"], 4)
        self.assertEqual(flach[Key("t1", "v1")]["rounds"], ["r1", "r2"])

        proRunde = verdict.judge(recs, {"t1": "v1"}, per_round=True).table
        self.assertEqual(set(proRunde), {Key("t1", "v1", "r1"), Key("t1", "v1", "r2")})
        self.assertEqual(proRunde[Key("t1", "v1", "r1")]["weighted_median"], 105)
        self.assertEqual(proRunde[Key("t1", "v1", "r2")]["weighted_median"], 205)

    def test_laeufe_ohne_runde_landen_in_einem_eigenen_topf(self):
        t = verdict.judge(runs_of("v1", 100, rnd=None), {"t1": "v1"}, per_round=True).table
        self.assertEqual(list(t), [Key("t1", "v1", "ohne-runde")])
        self.assertEqual(t[Key("t1", "v1", "ohne-runde")]["rounds"], [])


class Verlauf(unittest.TestCase):
    def test_verlauf_zeigt_delta_und_umgebungswechsel(self):
        b = judged(runs_of("v2", 40000, rnd="2026-05-02", models=["opus-4-5"]),
                   runs_of("v2", 44000, rnd="2026-08-14", models=["opus-5"]),
                   baseline="v2", per_round=True)
        reihe = b.history[Key("t1", "v2")]
        self.assertEqual([p["round"] for p in reihe], ["2026-05-02", "2026-08-14"])
        self.assertIsNone(reihe[0]["delta_to_prev_round"])
        self.assertAlmostEqual(reihe[1]["delta_to_prev_round"], 0.1, places=4)
        self.assertTrue(reihe[1]["env_changed"])
        self.assertIn("Modell/CLI gewechselt", report.render_trend(b.history))

    def test_eine_einzelne_runde_ergibt_keinen_verlauf(self):
        b = judged(runs_of("v2", 40000, rnd="2026-05-02"), baseline="v2", per_round=True)
        self.assertEqual(b.history, {})
        self.assertIn("Nur eine Messrunde", report.render_trend(b.history))

    def test_ohne_rundentrennung_gibt_es_keinen_verlauf(self):
        b = judged(runs_of("v2", 40000, rnd="2026-05-02"),
                   runs_of("v2", 44000, rnd="2026-08-14"), baseline="v2")
        self.assertEqual(b.history, {})


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
            runs.write_record(out, runs_of("v1", 100)[0])
            plans.save_plan(out, plans.new_plan("t1"))
            self.assertEqual(len(runs.load_records(out, "t1")), 1)


class Altdaten(unittest.TestCase):
    def test_laufdaten_ohne_umgebungsfelder_bleiben_lesbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rec = runs_of("v1", 100)[0]
            for f in ("round", "model", "cli_version", "prompt_sha"):
                del rec[f]
            import json
            (out / "t1__v1__01.json").write_text(json.dumps(rec), encoding="utf-8")
            geladen = runs.load_records(out, "t1")
            self.assertEqual(len(geladen), 1)
            self.assertIsNone(geladen[0]["round"])
            # und sie fallen durch die Auswertung, ohne dass ein Feld fehlt
            self.assertEqual(
                verdict.judge(geladen, {"t1": "v1"}).table[Key("t1", "v1")]["models"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
