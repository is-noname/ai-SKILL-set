#!/usr/bin/env python3
"""Tests fuer runs.py - stdlib only (kein pytest noetig).

IZG-T-132: build_record() ist der einzige Weg, wie ein Laufdatensatz entsteht. Getestet
wird, dass run/measure denselben Feldsatz erzeugen, dass die Laufnummern-Vergabe Luecken
respektiert, dass geschriebene Datensaetze unveraendert zurueckkommen und dass eine
unlesbare Datei im Ablageverzeichnis load_records() nicht zum Absturz bringt.

Alle Tests laufen gegen tmp_path (tempfile.TemporaryDirectory), nie gegen das echte
Ablageverzeichnis.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_runs.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import runs  # noqa: E402


def measured(session_id: str = "sid-1") -> dict:
    """Minimal-Fake fuer measure_session()'s Rueckgabe - alle Schluessel, die runs.py erwartet."""
    return {
        "session_id": session_id, "requests": 1, "usage": {"input": 10},
        "weighted_tokens": 10, "raw_tokens": 10, "cache_hit_rate": 0.0,
        "tool_calls": {}, "tool_result_tokens": {}, "skills_used": {},
        "subagent_output_tokens": 0, "first_timestamp": "t0", "last_timestamp": "t1",
    }


def exec_meta() -> dict:
    """Minimal-Fake fuer execute_run()'s Rueckgabe."""
    return {"duration_s": 1.5, "exit_code": 0, "cost_usd": 0.01,
            "num_turns": 3, "cli_subtype": "success", "stderr_tail": None}


class BuildRecord(unittest.TestCase):
    def test_run_und_measure_erzeugen_denselben_feldsatz(self):
        via_run = runs.build_record(task="t1", variant="v1", run=1, project=Path("/p"),
                                     outcome="ok", note="", measured=measured(),
                                     meta=exec_meta(), prompt_chars=42)
        via_measure = runs.build_record(task="t1", variant="v1", run=2, project=Path("/p"),
                                         outcome="ok", note="", measured=measured())
        self.assertEqual(set(via_run), set(via_measure))
        self.assertEqual(set(via_run), set(runs.RECORD_FIELDS))

    def test_measure_setzt_exec_felder_ausdruecklich_auf_none(self):
        rec = runs.build_record(task="t1", variant="v1", run=1, project=Path("/p"),
                                 outcome="ok", note="", measured=measured())
        self.assertIsNone(rec["cost_usd"])
        self.assertIsNone(rec["num_turns"])
        self.assertIsNone(rec["duration_s"])
        self.assertIsNone(rec["prompt_chars"])
        self.assertIn("cost_usd", rec)  # abwesend waere falsch, es muss explizit None sein

    def test_run_uebernimmt_exec_felder_aus_meta(self):
        rec = runs.build_record(task="t1", variant="v1", run=1, project=Path("/p"),
                                 outcome="ok", note="", measured=measured(),
                                 meta=exec_meta(), prompt_chars=42)
        self.assertEqual(rec["cost_usd"], 0.01)
        self.assertEqual(rec["prompt_chars"], 42)


class RunNumbering(unittest.TestCase):
    def test_naechste_freie_nummer_respektiert_luecken(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for run in (1, 2, 4):
                runs.write_record(out, runs.build_record(
                    task="t1", variant="v1", run=run, project=Path("/p"),
                    outcome="ok", note="", measured=measured()))
            # 1, 2, 4 belegt - naechste freie ist 3, nicht 5.
            self.assertEqual(runs.next_run_index(out, "t1", "v1"), 3)

    def test_leeres_verzeichnis_beginnt_bei_eins(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(runs.next_run_index(Path(tmp), "t1", "v1"), 1)


class WriteAndLoad(unittest.TestCase):
    def test_geschriebener_datensatz_kommt_unveraendert_zurueck(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rec = runs.build_record(task="t1", variant="v1", run=1, project=Path("/p"),
                                     outcome="ok", note="Testlauf", measured=measured(),
                                     meta=exec_meta(), prompt_chars=42)
            runs.write_record(out, rec)
            geladen = runs.load_records(out, "t1")
            self.assertEqual(len(geladen), 1)
            self.assertEqual(geladen[0], rec)

    def test_gemischte_herkunft_run_und_measure_in_derselben_variante(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            runs.write_record(out, runs.build_record(
                task="t1", variant="v1", run=1, project=Path("/p"), outcome="ok",
                note="", measured=measured("sid-run"), meta=exec_meta(), prompt_chars=42))
            runs.write_record(out, runs.build_record(
                task="t1", variant="v1", run=2, project=Path("/p"), outcome="ok",
                note="", measured=measured("sid-measure")))
            geladen = runs.load_records(out, "t1")
            self.assertEqual(len(geladen), 2)
            self.assertEqual({r["session_id"] for r in geladen}, {"sid-run", "sid-measure"})
            # beide haben denselben Feldsatz, obwohl einer per measure ohne exec-Metadaten kam.
            self.assertEqual(set(geladen[0]), set(geladen[1]))

    def test_unlesbare_datei_im_verzeichnis_bricht_load_records_nicht(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            runs.write_record(out, runs.build_record(
                task="t1", variant="v1", run=1, project=Path("/p"), outcome="ok",
                note="", measured=measured()))
            (out / "kaputt.json").write_text("{nicht valides json", encoding="utf-8")
            geladen = runs.load_records(out, "t1")
            self.assertEqual(len(geladen), 1)

    def test_leeres_verzeichnis_liefert_leere_liste(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(runs.load_records(Path(tmp) / "fehlt", "t1"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
