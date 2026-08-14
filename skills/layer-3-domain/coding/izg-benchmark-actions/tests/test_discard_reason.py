#!/usr/bin/env python3
"""Tests fuer discard_reason() - stdlib only (kein pytest noetig).

Kein subprocess, kein claude-Aufruf: discard_reason() nimmt nur das meta-dict
entgegen, das execute_run() zurueckgeben wuerde (oder ein von Hand gebautes Fake).
Getestet wird die Verwerfungsregel aus IZG-T-131: exit_code != 0 und cli_subtype
!= "success" fuehren zum Verwurf, ein sauberer Lauf nicht.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_discard_reason.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bench  # noqa: E402


def mk(exit_code: int = 0, cli_subtype: str | None = "success") -> dict:
    return {"exit_code": exit_code, "cli_subtype": cli_subtype}


class DiscardReason(unittest.TestCase):
    def test_sauberer_lauf_wird_nicht_verworfen(self):
        self.assertIsNone(bench.discard_reason(mk()))

    def test_exit_code_ungleich_null_wird_verworfen(self):
        reason = bench.discard_reason(mk(exit_code=1))
        self.assertIsNotNone(reason)
        self.assertIn("1", reason)

    def test_error_max_turns_wird_verworfen(self):
        reason = bench.discard_reason(mk(cli_subtype="error_max_turns"))
        self.assertIsNotNone(reason)
        self.assertIn("error_max_turns", reason)

    def test_error_during_execution_wird_verworfen(self):
        reason = bench.discard_reason(mk(cli_subtype="error_during_execution"))
        self.assertIsNotNone(reason)
        self.assertIn("error_during_execution", reason)

    def test_fehlender_subtype_bei_exit_null_wird_nicht_verworfen(self):
        # payload konnte nicht geparst werden - subtype fehlt, aber der Prozess lief sauber durch.
        self.assertIsNone(bench.discard_reason(mk(cli_subtype=None)))

    def test_exit_code_hat_vorrang_vor_subtype(self):
        reason = bench.discard_reason(mk(exit_code=2, cli_subtype="success"))
        self.assertIn("2", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
