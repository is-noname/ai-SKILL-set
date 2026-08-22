#!/usr/bin/env python3
"""Tests fuer den Messlauf - stdlib only (kein pytest noetig).

Kein subprocess, kein claude-Aufruf, keine Kosten: die Ausfuehrung wird ueber den seam
`measurement.Executor` durch einen Fake ersetzt, der Timeout, Fehler-Exitcode,
Abbruch-Subtype und fehlendes Transcript auf Kommando liefert. Damit ist nicht nur die
Verwerfungsregel selbst geprueft (IZG-T-131), sondern auch ihr Aufrufkontext: dass ein
verworfener Lauf keine Laufnummer belegt, dass die Umschaltung vor *jedem* Lauf laeuft
und dass ueberhaupt keine Datei entsteht, wo nichts verbucht werden darf.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_measurement.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measurement  # noqa: E402
import runs  # noqa: E402


def meta(exit_code: int = 0, cli_subtype: str | None = "success") -> dict:
    return {"exit_code": exit_code, "cli_subtype": cli_subtype, "duration_s": 12.0,
            "cost_usd": 0.5, "num_turns": 4, "stderr_tail": None}


def measured(weighted: int = 1000, session_id: str = "sid") -> dict:
    """Minimal-Fake fuer die Rueckgabe von Executor.measure() - alle Schluessel des Schemas."""
    return {"session_id": session_id, "requests": 3, "usage": {}, "weighted_tokens": weighted,
            "raw_tokens": 900, "cache_hit_rate": 0.5, "tool_calls": {},
            "tool_result_tokens": 0, "skills_used": [], "subagent_output_tokens": 0,
            "first_timestamp": None, "last_timestamp": None}


class FakeExecutor:
    """Ausfuehrung ohne Aussenwelt. `plan` legt je Lauf fest, was passiert.

    Ein Eintrag ist entweder ein meta-dict (Lauf laeuft) oder "timeout".
    """

    def __init__(self, *plan):
        self.plan = list(plan)
        self.log: list[tuple[str, str]] = []

    def _next(self):
        return self.plan.pop(0) if self.plan else meta()

    def switch(self, setup: str, project: Path) -> None:
        self.log.append(("setup", setup))

    def start(self, spec, session_id: str) -> dict:
        self.log.append(("start", session_id))
        step = self._next()
        if step == "timeout":
            raise subprocess.TimeoutExpired(cmd="claude", timeout=spec.timeout)
        return step

    def measure(self, project: Path, session_id: str) -> dict:
        self.log.append(("measure", session_id))
        return measured(session_id=session_id)


class FehlendesTranscript(FakeExecutor):
    """Der Lauf laeuft sauber durch, das Transcript fehlt trotzdem."""

    def measure(self, project: Path, session_id: str) -> dict:
        raise FileNotFoundError(f"Kein Transcript fuer {session_id}")


def spec(**kw) -> measurement.RunSpec:
    values = {"task": "t1", "variant": "v1", "project": Path("/tmp/projekt"),
             "prompt": "Testaufgabe", "env": {"round": "2026-08-15", "model": "opus",
                                              "cli_version": "1.0", "prompt_sha": "abc"}}
    values.update(kw)
    return measurement.RunSpec(**values)


class Verwerfungsregel(unittest.TestCase):
    """discard_reason() selbst - die Regel ohne ihren Kontext."""

    def test_sauberer_lauf_wird_nicht_verworfen(self):
        self.assertIsNone(measurement.discard_reason(meta()))

    def test_exit_code_ungleich_null_wird_verworfen(self):
        self.assertIn("1", measurement.discard_reason(meta(exit_code=1)))

    def test_error_max_turns_wird_verworfen(self):
        self.assertIn("error_max_turns", measurement.discard_reason(meta(cli_subtype="error_max_turns")))

    def test_error_during_execution_wird_verworfen(self):
        reason = measurement.discard_reason(meta(cli_subtype="error_during_execution"))
        self.assertIn("error_during_execution", reason)

    def test_fehlender_subtype_bei_exit_null_wird_nicht_verworfen(self):
        # payload konnte nicht geparst werden - subtype fehlt, aber der Prozess lief sauber durch.
        self.assertIsNone(measurement.discard_reason(meta(cli_subtype=None)))

    def test_exit_code_hat_vorrang_vor_subtype(self):
        self.assertIn("2", measurement.discard_reason(meta(exit_code=2, cli_subtype="success")))


class Schleife(unittest.TestCase):
    """Die Regel in ihrem Aufrufkontext - frueher nur ueber einen echten claude-Lauf erreichbar."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def drive(self, executor, repeats=1, **kw):
        return list(measurement.drive(self.out, spec(**kw), repeats, executor))

    def test_sauberer_lauf_wird_verbucht(self):
        res = self.drive(FakeExecutor())[0]
        self.assertIsNone(res.discarded)
        self.assertEqual(res.run, 1)
        self.assertTrue(res.path.is_file())
        self.assertEqual(res.record["task"], "t1")
        self.assertEqual(res.record["prompt_chars"], len("Testaufgabe"))

    def test_umgebungsfelder_landen_im_datensatz(self):
        rec = self.drive(FakeExecutor())[0].record
        self.assertEqual(rec["round"], "2026-08-15")
        self.assertEqual(rec["model"], "opus")
        self.assertEqual(rec["prompt_sha"], "abc")

    def test_wiederholungen_zaehlen_die_laufnummern_hoch(self):
        results = self.drive(FakeExecutor(), 3)
        self.assertEqual([e.run for e in results], [1, 2, 3])
        self.assertEqual(len(runs.load_records(self.out, "t1")), 3)

    def test_verworfener_lauf_belegt_keine_laufnummer(self):
        results = self.drive(FakeExecutor(meta(exit_code=1), meta()), 2)
        self.assertIsNotNone(results[0].discarded)
        self.assertIsNone(results[1].discarded)
        # Beide Versuche bekommen Laufnummer 1 - erst das Schreiben verbraucht sie.
        self.assertEqual([e.run for e in results], [1, 1])
        self.assertEqual(len(runs.load_records(self.out, "t1")), 1)

    def test_timeout_wird_verworfen_und_nicht_verbucht(self):
        res = self.drive(FakeExecutor("timeout"))[0]
        self.assertIn("Timeout", res.discarded)
        self.assertIsNone(res.record)
        self.assertEqual(list(self.out.glob("*.json")), [])

    def test_timeout_nennt_die_grenze(self):
        res = self.drive(FakeExecutor("timeout"), timeout=120)[0]
        self.assertIn("120", res.discarded)

    def test_abbruch_subtype_wird_verworfen(self):
        res = self.drive(FakeExecutor(meta(cli_subtype="error_max_turns")))[0]
        self.assertIn("error_max_turns", res.discarded)
        self.assertEqual(list(self.out.glob("*.json")), [])

    def test_fehlendes_transcript_wird_verworfen(self):
        res = self.drive(FehlendesTranscript())[0]
        self.assertIn("Transcript", res.discarded)
        self.assertEqual(list(self.out.glob("*.json")), [])

    def test_timeout_ueberspringt_die_messung(self):
        executor = FakeExecutor("timeout")
        self.drive(executor)
        self.assertNotIn("measure", [step for step, _ in executor.log])

    def test_umschaltung_laeuft_vor_jedem_lauf(self):
        executor = FakeExecutor()
        self.drive(executor, 3, setup="cp variante .claude/")
        steps = [s for s, _ in executor.log]
        self.assertEqual(steps.count("setup"), 3)
        self.assertEqual(steps[0], "setup")
        self.assertEqual(steps[1], "start")

    def test_umschaltung_laeuft_auch_vor_einem_verworfenen_lauf(self):
        executor = FakeExecutor(meta(exit_code=1), meta())
        self.drive(executor, 2, setup="cp variante .claude/")
        self.assertEqual([s for s, _ in executor.log].count("setup"), 2)

    def test_ohne_setup_wird_nicht_umgeschaltet(self):
        executor = FakeExecutor()
        self.drive(executor, 2)
        self.assertNotIn("setup", [s for s, _ in executor.log])

    def test_jeder_lauf_bekommt_eine_eigene_session(self):
        executor = FakeExecutor()
        results = self.drive(executor, 3)
        self.assertEqual(len({e.session_id for e in results}), 3)

    def test_notify_wird_vor_dem_start_gerufen(self):
        notified: list[tuple] = []
        executor = FakeExecutor()
        list(measurement.drive(self.out, spec(), 2, executor,
                               new_session=lambda: "feste-sid",
                               notify=lambda i, g, r, s: notified.append((i, g, r, s))))
        self.assertEqual(notified[0], (1, 2, 1, "feste-sid"))
        self.assertEqual(notified[1][:3], (2, 2, 2))

    def test_generator_laeuft_erst_beim_verbrauchen(self):
        # Wichtig fuer die Ausgabe waehrend eines langen Laufs: nichts passiert auf Vorrat.
        executor = FakeExecutor()
        it = measurement.drive(self.out, spec(), 3, executor)
        self.assertEqual(executor.log, [])
        next(it)
        self.assertEqual([s for s, _ in executor.log], ["start", "measure"])

    def test_datensatz_haelt_den_feldsatz_ein(self):
        rec = self.drive(FakeExecutor())[0].record
        self.assertEqual(set(rec), set(runs.RECORD_FIELDS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
