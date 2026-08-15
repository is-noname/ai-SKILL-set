#!/usr/bin/env python3
"""Tests fuer die Basiswahl - stdlib only (kein pytest noetig).

Die Basis entscheidet, worauf sich jedes Urteil bezieht. Vergisst jemand `--baseline`,
faellt das Urteil klaglos gegen eine andere Variante aus und die Tabelle sieht genauso
plausibel aus. Getestet wird deshalb die Rangfolge: Kommandozeile schlaegt Messplan,
Messplan schlaegt Alphabet - und dass der Alphabet-Fall gemeldet wird.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_baseline.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import plans  # noqa: E402
import verdict  # noqa: E402


class RecordBaseline(unittest.TestCase):
    def test_ergaenzt_leeren_plan(self):
        plan = plans.new_plan("t1")
        self.assertIn("ergaenzt", plans.record_baseline(plan, "basis"))
        self.assertEqual(plan["baseline"], "basis")

    def test_meldet_wechsel(self):
        plan = plans.new_plan("t1")
        plans.record_baseline(plan, "basis")
        note = plans.record_baseline(plan, "v2")
        self.assertIn("basis", note)
        self.assertIn("v2", note)
        self.assertEqual(plan["baseline"], "v2")

    def test_schweigt_bei_gleicher_basis(self):
        plan = plans.new_plan("t1")
        plans.record_baseline(plan, "basis")
        self.assertIsNone(plans.record_baseline(plan, "basis"))

    def test_none_laesst_plan_unberuehrt(self):
        plan = plans.new_plan("t1")
        plans.record_baseline(plan, "basis")
        self.assertIsNone(plans.record_baseline(plan, None))
        self.assertEqual(plan["baseline"], "basis")


class ResolveBaselines(unittest.TestCase):
    def test_kommandozeile_schlaegt_messplan(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            plan = plans.new_plan("t1")
            plans.record_baseline(plan, "aus-plan")
            plans.save_plan(out, plan)
            resolved, notes = plans.resolve_baselines(out, ["t1"], "vom-aufruf")
            self.assertEqual(resolved["t1"], "vom-aufruf")
            self.assertEqual(len(notes), 1)
            self.assertIn("aus-plan", notes[0])
            self.assertIn("vom-aufruf", notes[0])
            self.assertEqual(plans.load_plan(out, "t1")["baseline"], "vom-aufruf")

    def test_messplan_wenn_aufruf_schweigt(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            plan = plans.new_plan("t1")
            plans.record_baseline(plan, "aus-plan")
            plans.save_plan(out, plan)
            resolved, notes = plans.resolve_baselines(out, ["t1"], None)
            self.assertEqual(resolved["t1"], "aus-plan")
            self.assertEqual(notes, [])

    def test_ohne_basis_wird_gemeldet(self):
        with tempfile.TemporaryDirectory() as d:
            resolved, notes = plans.resolve_baselines(Path(d), ["t1"], None)
            self.assertIsNone(resolved["t1"])
            self.assertEqual(len(notes), 1)
            self.assertIn("--baseline", notes[0])

    def test_je_task_eine_eigene_basis(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            for task, base in (("t1", "b1"), ("t2", "b2")):
                plan = plans.new_plan(task)
                plans.record_baseline(plan, base)
                plans.save_plan(out, plan)
            resolved, _ = plans.resolve_baselines(out, ["t1", "t2"], None)
            self.assertEqual(resolved, {"t1": "b1", "t2": "b2"})


class SelectBase(unittest.TestCase):
    def test_mapping_je_task(self):
        variants = [{"task": "t2", "variant": v} for v in ("a", "b2")]
        self.assertEqual(verdict.select_base(variants, {"t1": "b1", "t2": "b2"}), "b2")

    def test_einzelwert_gilt_fuer_alle(self):
        variants = [{"task": "t1", "variant": v} for v in ("a", "basis")]
        self.assertEqual(verdict.select_base(variants, {"t1": "basis"}), "basis")

    def test_alphabet_wenn_basis_fehlt(self):
        variants = [{"task": "t1", "variant": v} for v in ("b", "a")]
        self.assertEqual(verdict.select_base(variants, None), "a")

    def test_alphabet_wenn_basis_nicht_gemessen(self):
        """Eine Basis, zu der keine Laeufe vorliegen, darf nicht stillschweigend gelten."""
        variants = [{"task": "t1", "variant": v} for v in ("b", "a")]
        self.assertEqual(verdict.select_base(variants, {"t1": "nie-gemessen"}), "a")


if __name__ == "__main__":
    unittest.main(verbosity=2)
