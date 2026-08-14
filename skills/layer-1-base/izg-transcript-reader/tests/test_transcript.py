#!/usr/bin/env python3
"""Tests fuer transcript.py - stdlib only (kein pytest noetig).

Zusammengefuehrt aus den bisherigen Suiten von izg-improve-token-usage
(analyze_transcript.py) und izg-benchmark-actions (transcript.py), als die
beiden Adapter zu diesem gemeinsamen Modul vereinigt wurden (IZG-T-139).
Baut Fixture-JSONL von Hand, liest sie ueber explizite Pfade - kein
HOME-Zugriff, keine echte Claude-Code-Installation noetig.

    python3 -m unittest discover skills/layer-1-base/izg-transcript-reader/tests
    python3 skills/layer-1-base/izg-transcript-reader/tests/test_transcript.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import transcript as t  # noqa: E402

ENTRIES = [
    # 1: requestId r1, zwei tool_use-Bloecke (Bash, Skill)
    {
        "type": "assistant", "timestamp": "2026-08-14T10:00:00Z", "requestId": "r1",
        "message": {
            "usage": {"input_tokens": 100, "cache_read_input_tokens": 10,
                      "cache_creation_input_tokens": 5, "output_tokens": 20},
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
                {"type": "tool_use", "id": "t3", "name": "Skill",
                 "input": {"skill": "izg-transcript-reader"}},
            ],
        },
    },
    # 2: gleiche requestId r1, andere Zahlen -> muss ignoriert werden (Entdopplung)
    {
        "type": "assistant", "timestamp": "2026-08-14T10:00:01Z", "requestId": "r1",
        "message": {
            "usage": {"input_tokens": 999, "cache_read_input_tokens": 999,
                      "cache_creation_input_tokens": 999, "output_tokens": 999},
            "content": [],
        },
    },
    # 3: keine requestId, uuid-Fallback
    {
        "type": "assistant", "timestamp": "2026-08-14T10:00:02Z", "uuid": "u1",
        "message": {
            "usage": {"input_tokens": 50, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 10},
            "content": [{"type": "tool_use", "id": "t2", "name": "Read",
                        "input": {"file_path": "x"}}],
        },
    },
    # 4: Subagent-Block (isSidechain), zweiter Bash-Aufruf mit gleichem Label wie t1
    {
        "type": "assistant", "timestamp": "2026-08-14T10:00:03Z", "requestId": "r2",
        "isSidechain": True,
        "message": {
            "usage": {"input_tokens": 30, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 15},
            "content": [{"type": "tool_use", "id": "t4", "name": "Bash",
                        "input": {"command": "ls"}}],
        },
    },
    # 5: tool_result zu t1, content als str
    {
        "type": "user", "timestamp": "2026-08-14T10:00:04Z",
        "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                 "content": "hello world"}]},
    },
    # 6: tool_result zu t2, content als list
    {
        "type": "user", "timestamp": "2026-08-14T10:00:05Z",
        "message": {"content": [{"type": "tool_result", "tool_use_id": "t2",
                                 "content": [{"text": "yes"}]}]},
    },
    # 7: tool_result zu t4, content als dict (sidechain-Aufruf)
    {
        "type": "user", "timestamp": "2026-08-14T10:00:06Z",
        "message": {"content": [{"type": "tool_result", "tool_use_id": "t4",
                                 "content": {"a": 1}}]},
    },
    # 8: tool_result ohne passenden tool_use
    {
        "type": "user", "timestamp": "2026-08-14T10:00:07Z",
        "message": {"content": [{"type": "tool_result", "tool_use_id": "orphan",
                                 "content": "verwaist"}]},
    },
]


def write_fixture(path: Path) -> None:
    lines = [
        json.dumps(ENTRIES[0], ensure_ascii=False),
        "{not valid json",
        "",
        json.dumps(ENTRIES[1], ensure_ascii=False),
        json.dumps(ENTRIES[2], ensure_ascii=False),
        json.dumps(ENTRIES[3], ensure_ascii=False),
        json.dumps(ENTRIES[4], ensure_ascii=False),
        "   ",
        json.dumps(ENTRIES[5], ensure_ascii=False),
        json.dumps(ENTRIES[6], ensure_ascii=False),
        json.dumps(ENTRIES[7], ensure_ascii=False),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


class FindTranscripts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "sess-1.jsonl").write_text("{}", encoding="utf-8")
        (self.base / "sess-2.jsonl").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ohne_base_dir_fehlender_ordner_liefert_leere_liste(self):
        files = t.find_transcripts(Path("/nicht/vorhanden"), None,
                                    base_dir=self.base / "nope")
        self.assertEqual(files, [])

    def test_base_dir_wird_statt_home_verwendet(self):
        files = t.find_transcripts(Path("egal"), None, base_dir=self.base)
        self.assertEqual({f.name for f in files}, {"sess-1.jsonl", "sess-2.jsonl"})

    def test_session_filtert_auf_eine_datei(self):
        files = t.find_transcripts(Path("egal"), None, "sess-1", base_dir=self.base)
        self.assertEqual([f.name for f in files], ["sess-1.jsonl"])

    def test_session_ohne_treffer_liefert_leere_liste(self):
        files = t.find_transcripts(Path("egal"), None, "sess-nope", base_dir=self.base)
        self.assertEqual(files, [])

    def test_limit_begrenzt_anzahl(self):
        files = t.find_transcripts(Path("egal"), 1, base_dir=self.base)
        self.assertEqual(len(files), 1)


class TranscriptPath(unittest.TestCase):
    def test_projekt_slug_ersetzt_sonderzeichen(self):
        p = t.transcript_path(Path("/tmp/mein projekt"), "abc")
        self.assertTrue(str(p).endswith("abc.jsonl"))
        self.assertNotIn(" ", p.parent.name)


class ReadSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sess-1.jsonl"
        write_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fehlende_datei_wirft_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            t.read_session(self.path.parent / "nope.jsonl", "sess-1")

    def test_requestid_entdopplung_ignoriert_zweiten_eintrag(self):
        su = t.read_session(self.path, "sess-1")
        # r1, u1, r2 - der doppelte r1-Eintrag zaehlt nicht mit
        self.assertEqual(su.requests, 3)

    def test_usage_summe_ueber_alle_requests(self):
        su = t.read_session(self.path, "sess-1")
        self.assertEqual(su.usage["input"], 100 + 50 + 30)
        self.assertEqual(su.usage["cache_read"], 10)
        self.assertEqual(su.usage["cache_creation"], 5)
        self.assertEqual(su.usage["output"], 20 + 10 + 15)

    def test_uuid_fallback_wird_gezaehlt(self):
        su = t.read_session(self.path, "sess-1")
        self.assertEqual(su.tool_calls.get("Read"), 1)

    def test_sidechain_output_getrennt_verbucht(self):
        su = t.read_session(self.path, "sess-1")
        self.assertEqual(su.subagent_output_tokens, 15)

    def test_skill_nutzung_erfasst(self):
        su = t.read_session(self.path, "sess-1")
        self.assertEqual(su.skills_used, {"izg-transcript-reader": 1})

    def test_tool_result_ohne_passenden_tool_use_wird_stillschweigend_verworfen(self):
        su = t.read_session(self.path, "sess-1")
        self.assertNotIn("orphan", su.tool_result_tokens)

    def test_content_als_str_wird_gezaehlt(self):
        su = t.read_session(self.path, "sess-1")
        # t1 ("hello world") und t4 ({"a": 1}) sind beide Bash
        expected = 11 // t.CHARS_PER_TOKEN + len(json.dumps({"a": 1}, ensure_ascii=False)) // t.CHARS_PER_TOKEN
        self.assertEqual(su.tool_result_tokens["Bash"], expected)

    def test_content_als_list_wird_gezaehlt(self):
        su = t.read_session(self.path, "sess-1")
        expected_chars = len(json.dumps({"text": "yes"}, ensure_ascii=False))
        self.assertEqual(su.tool_result_tokens["Read"], expected_chars // t.CHARS_PER_TOKEN)

    def test_zeitstempel_spanne_ignoriert_kaputte_und_leere_zeilen(self):
        su = t.read_session(self.path, "sess-1")
        self.assertEqual(su.first_timestamp, "2026-08-14T10:00:00Z")
        self.assertEqual(su.last_timestamp, "2026-08-14T10:00:07Z")

    def test_session_id_wird_durchgereicht(self):
        su = t.read_session(self.path, "sess-1")
        self.assertEqual(su.session_id, "sess-1")


class ParseEntries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sess-1.jsonl"
        write_fixture(self.path)
        self.parsed = t.parse_entries(t.read_entries([self.path]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_requestid_entdopplung(self):
        self.assertEqual(len(self.parsed.usage_by_request), 3)

    def test_wiederholte_aufrufe_ueber_call_label_gruppierbar(self):
        # t1 und t4 sind beides Bash-Aufrufe mit command "ls" -> gleiches Label
        self.assertEqual(self.parsed.label_counts["Bash"]["ls"], 2)

    def test_sidechain_markierung_je_tool_call(self):
        sidechain_tools = [name for name, _, sc in self.parsed.tool_calls.values() if sc]
        self.assertEqual(sidechain_tools, ["Bash"])

    def test_since_until_filtern_read_entries(self):
        entries = list(t.read_entries([self.path], since="2026-08-14T10:00:05Z"))
        self.assertTrue(all(e.get("timestamp", "") >= "2026-08-14T10:00:05Z" for e in entries))
        self.assertTrue(entries)


class UsageTotalsAndEstimate(unittest.TestCase):
    def test_usage_totals_summiert_ueber_requests(self):
        totals = t.usage_totals({
            "r1": {"input": 10, "cache_read": 1, "cache_creation": 2, "output": 3},
            "r2": {"input": 20, "cache_read": 4, "cache_creation": 5, "output": 6},
        })
        self.assertEqual(totals, {"input": 30, "cache_read": 5, "cache_creation": 7, "output": 9})

    def test_estimate_tool_tokens_teilt_zeichen_durch_chars_per_token(self):
        calls = t.estimate_tool_tokens(
            {"t1": ("Bash", "ls", False)}, {"t1": 40},
        )
        self.assertEqual(calls, [{"tool": "Bash", "label": "ls", "tokens": 10, "sidechain": False}])


class ContentLen(unittest.TestCase):
    def test_str(self):
        self.assertEqual(t.content_len("abcd"), 4)

    def test_list_von_blocktexten(self):
        self.assertEqual(t.content_len(["ab", "cd"]), 4)

    def test_list_von_dict_bloecken(self):
        blocks = [{"content": "xy"}]
        self.assertEqual(t.content_len(blocks), len(json.dumps("xy", ensure_ascii=False)))

    def test_dict(self):
        self.assertEqual(t.content_len({"a": 1}), len(json.dumps({"a": 1}, ensure_ascii=False)))

    def test_sonstiges_liefert_null(self):
        self.assertEqual(t.content_len(None), 0)
        self.assertEqual(t.content_len(42), 0)


class CallLabel(unittest.TestCase):
    def test_read_edit_write_nutzen_file_path(self):
        self.assertEqual(t.call_label("Read", {"file_path": "/a/b.py"}), "/a/b.py")
        self.assertEqual(t.call_label("Write", {"file_path": "/a/c.py"}), "/a/c.py")

    def test_bash_kuerzt_und_ersetzt_newlines(self):
        label = t.call_label("Bash", {"command": "echo a\necho b"})
        self.assertEqual(label, "echo a echo b")

    def test_bash_kappt_bei_120_zeichen(self):
        label = t.call_label("Bash", {"command": "x" * 200})
        self.assertEqual(len(label), 120)

    def test_grep_glob_kombiniert_pattern_und_pfad(self):
        self.assertEqual(t.call_label("Grep", {"pattern": "foo", "path": "src"}), "foo @ src")

    def test_agent_kombiniert_typ_und_beschreibung(self):
        label = t.call_label("Agent", {"subagent_type": "general-purpose", "description": "such was"})
        self.assertEqual(label, "general-purpose: such was")

    def test_skill_nutzt_skillnamen(self):
        self.assertEqual(t.call_label("Skill", {"skill": "izg-domain-modeling"}), "izg-domain-modeling")

    def test_unbekanntes_tool_faellt_auf_json_zurueck(self):
        label = t.call_label("Sonstiges", {"x": 1})
        self.assertEqual(label, json.dumps({"x": 1}, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
