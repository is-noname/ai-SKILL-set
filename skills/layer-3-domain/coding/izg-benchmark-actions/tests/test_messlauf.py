#!/usr/bin/env python3
"""Tests fuer den Messlauf - stdlib only (kein pytest noetig).

Kein subprocess, kein claude-Aufruf, keine Kosten: die Ausfuehrung wird ueber den seam
`messlauf.Ausfuehrung` durch einen Fake ersetzt, der Timeout, Fehler-Exitcode,
Abbruch-Subtype und fehlendes Transcript auf Kommando liefert. Damit ist nicht nur die
Verwerfungsregel selbst geprueft (IZG-T-131), sondern auch ihr Aufrufkontext: dass ein
verworfener Lauf keine Laufnummer belegt, dass die Umschaltung vor *jedem* Lauf laeuft
und dass ueberhaupt keine Datei entsteht, wo nichts verbucht werden darf.

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_messlauf.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import messlauf  # noqa: E402
import runs  # noqa: E402


def meta(exit_code: int = 0, cli_subtype: str | None = "success") -> dict:
    return {"exit_code": exit_code, "cli_subtype": cli_subtype, "duration_s": 12.0,
            "cost_usd": 0.5, "num_turns": 4, "stderr_tail": None}


def measured(weighted: int = 1000, session_id: str = "sid") -> dict:
    """Minimal-Fake fuer die Rueckgabe von Ausfuehrung.miss() - alle Schluessel des Schemas."""
    return {"session_id": session_id, "requests": 3, "usage": {}, "weighted_tokens": weighted,
            "raw_tokens": 900, "cache_hit_rate": 0.5, "tool_calls": {},
            "tool_result_tokens": 0, "skills_used": [], "subagent_output_tokens": 0,
            "first_timestamp": None, "last_timestamp": None}


class FakeAusfuehrung:
    """Ausfuehrung ohne Aussenwelt. `plan` legt je Lauf fest, was passiert.

    Ein Eintrag ist entweder ein meta-dict (Lauf laeuft) oder "timeout".
    """

    def __init__(self, *plan):
        self.plan = list(plan)
        self.protokoll: list[tuple[str, str]] = []

    def _naechster(self):
        return self.plan.pop(0) if self.plan else meta()

    def schalte_um(self, setup: str, project: Path) -> None:
        self.protokoll.append(("setup", setup))

    def starte(self, auftrag, session_id: str) -> dict:
        self.protokoll.append(("start", session_id))
        schritt = self._naechster()
        if schritt == "timeout":
            raise subprocess.TimeoutExpired(cmd="claude", timeout=auftrag.timeout)
        return schritt

    def miss(self, project: Path, session_id: str) -> dict:
        self.protokoll.append(("miss", session_id))
        return measured(session_id=session_id)


class FehlendesTranscript(FakeAusfuehrung):
    """Der Lauf laeuft sauber durch, das Transcript fehlt trotzdem."""

    def miss(self, project: Path, session_id: str) -> dict:
        raise FileNotFoundError(f"Kein Transcript fuer {session_id}")


def auftrag(**kw) -> messlauf.Laufauftrag:
    werte = {"task": "t1", "variant": "v1", "project": Path("/tmp/projekt"),
             "prompt": "Testaufgabe", "env": {"round": "2026-08-15", "model": "opus",
                                              "cli_version": "1.0", "prompt_sha": "abc"}}
    werte.update(kw)
    return messlauf.Laufauftrag(**werte)


class Verwerfungsregel(unittest.TestCase):
    """discard_reason() selbst - die Regel ohne ihren Kontext."""

    def test_sauberer_lauf_wird_nicht_verworfen(self):
        self.assertIsNone(messlauf.discard_reason(meta()))

    def test_exit_code_ungleich_null_wird_verworfen(self):
        self.assertIn("1", messlauf.discard_reason(meta(exit_code=1)))

    def test_error_max_turns_wird_verworfen(self):
        self.assertIn("error_max_turns", messlauf.discard_reason(meta(cli_subtype="error_max_turns")))

    def test_error_during_execution_wird_verworfen(self):
        grund = messlauf.discard_reason(meta(cli_subtype="error_during_execution"))
        self.assertIn("error_during_execution", grund)

    def test_fehlender_subtype_bei_exit_null_wird_nicht_verworfen(self):
        # payload konnte nicht geparst werden - subtype fehlt, aber der Prozess lief sauber durch.
        self.assertIsNone(messlauf.discard_reason(meta(cli_subtype=None)))

    def test_exit_code_hat_vorrang_vor_subtype(self):
        self.assertIn("2", messlauf.discard_reason(meta(exit_code=2, cli_subtype="success")))


class Schleife(unittest.TestCase):
    """Die Regel in ihrem Aufrufkontext - frueher nur ueber einen echten claude-Lauf erreichbar."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def fahre(self, ausf, wiederholungen=1, **kw):
        return list(messlauf.fahre(self.out, auftrag(**kw), wiederholungen, ausf))

    def test_sauberer_lauf_wird_verbucht(self):
        erg = self.fahre(FakeAusfuehrung())[0]
        self.assertIsNone(erg.verworfen)
        self.assertEqual(erg.run, 1)
        self.assertTrue(erg.pfad.is_file())
        self.assertEqual(erg.record["task"], "t1")
        self.assertEqual(erg.record["prompt_chars"], len("Testaufgabe"))

    def test_umgebungsfelder_landen_im_datensatz(self):
        rec = self.fahre(FakeAusfuehrung())[0].record
        self.assertEqual(rec["round"], "2026-08-15")
        self.assertEqual(rec["model"], "opus")
        self.assertEqual(rec["prompt_sha"], "abc")

    def test_wiederholungen_zaehlen_die_laufnummern_hoch(self):
        ergs = self.fahre(FakeAusfuehrung(), 3)
        self.assertEqual([e.run for e in ergs], [1, 2, 3])
        self.assertEqual(len(list(self.out.glob("*.json"))), 3)

    def test_verworfener_lauf_belegt_keine_laufnummer(self):
        ergs = self.fahre(FakeAusfuehrung(meta(exit_code=1), meta()), 2)
        self.assertIsNotNone(ergs[0].verworfen)
        self.assertIsNone(ergs[1].verworfen)
        # Beide Versuche bekommen Laufnummer 1 - erst das Schreiben verbraucht sie.
        self.assertEqual([e.run for e in ergs], [1, 1])
        self.assertEqual(len(list(self.out.glob("*.json"))), 1)

    def test_timeout_wird_verworfen_und_nicht_verbucht(self):
        erg = self.fahre(FakeAusfuehrung("timeout"))[0]
        self.assertIn("Timeout", erg.verworfen)
        self.assertIsNone(erg.record)
        self.assertEqual(list(self.out.glob("*.json")), [])

    def test_timeout_nennt_die_grenze(self):
        erg = self.fahre(FakeAusfuehrung("timeout"), timeout=120)[0]
        self.assertIn("120", erg.verworfen)

    def test_abbruch_subtype_wird_verworfen(self):
        erg = self.fahre(FakeAusfuehrung(meta(cli_subtype="error_max_turns")))[0]
        self.assertIn("error_max_turns", erg.verworfen)
        self.assertEqual(list(self.out.glob("*.json")), [])

    def test_fehlendes_transcript_wird_verworfen(self):
        erg = self.fahre(FehlendesTranscript())[0]
        self.assertIn("Transcript", erg.verworfen)
        self.assertEqual(list(self.out.glob("*.json")), [])

    def test_timeout_ueberspringt_die_messung(self):
        ausf = FakeAusfuehrung("timeout")
        self.fahre(ausf)
        self.assertNotIn("miss", [schritt for schritt, _ in ausf.protokoll])

    def test_umschaltung_laeuft_vor_jedem_lauf(self):
        ausf = FakeAusfuehrung()
        self.fahre(ausf, 3, setup="cp variante .claude/")
        schritte = [s for s, _ in ausf.protokoll]
        self.assertEqual(schritte.count("setup"), 3)
        self.assertEqual(schritte[0], "setup")
        self.assertEqual(schritte[1], "start")

    def test_umschaltung_laeuft_auch_vor_einem_verworfenen_lauf(self):
        ausf = FakeAusfuehrung(meta(exit_code=1), meta())
        self.fahre(ausf, 2, setup="cp variante .claude/")
        self.assertEqual([s for s, _ in ausf.protokoll].count("setup"), 2)

    def test_ohne_setup_wird_nicht_umgeschaltet(self):
        ausf = FakeAusfuehrung()
        self.fahre(ausf, 2)
        self.assertNotIn("setup", [s for s, _ in ausf.protokoll])

    def test_jeder_lauf_bekommt_eine_eigene_session(self):
        ausf = FakeAusfuehrung()
        ergs = self.fahre(ausf, 3)
        self.assertEqual(len({e.session_id for e in ergs}), 3)

    def test_melde_wird_vor_dem_start_gerufen(self):
        gemeldet: list[tuple] = []
        ausf = FakeAusfuehrung()
        list(messlauf.fahre(self.out, auftrag(), 2, ausf,
                            neue_session=lambda: "feste-sid",
                            melde=lambda i, g, r, s: gemeldet.append((i, g, r, s))))
        self.assertEqual(gemeldet[0], (1, 2, 1, "feste-sid"))
        self.assertEqual(gemeldet[1][:3], (2, 2, 2))

    def test_generator_laeuft_erst_beim_verbrauchen(self):
        # Wichtig fuer die Ausgabe waehrend eines langen Laufs: nichts passiert auf Vorrat.
        ausf = FakeAusfuehrung()
        lauf = messlauf.fahre(self.out, auftrag(), 3, ausf)
        self.assertEqual(ausf.protokoll, [])
        next(lauf)
        self.assertEqual([s for s, _ in ausf.protokoll], ["start", "miss"])

    def test_datensatz_haelt_den_feldsatz_ein(self):
        rec = self.fahre(FakeAusfuehrung())[0].record
        self.assertEqual(set(rec), set(runs.RECORD_FIELDS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
