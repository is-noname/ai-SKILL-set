#!/usr/bin/env python3
"""Tests fuer transcript.read_session() - stdlib only (kein pytest noetig).

Baut eine Fixture-JSONL von Hand und liest sie ueber einen expliziten Pfad -
kein HOME-Zugriff, keine echte Claude-Code-Installation noetig. Deckt die
Eigenheiten des Formats ab, die vorher in bench.py und analyze_transcript.py
je einzeln nachgebaut waren: requestId-Entdopplung mit uuid-Fallback,
isSidechain, tool_use/tool_result-Paarung inklusive Waisen, kaputte/leere
Zeilen und die drei content-Gestalten (str/list/dict).

    python3 -m unittest discover skills/layer-3-domain/coding/izg-benchmark-actions/tests
    python3 skills/layer-3-domain/coding/izg-benchmark-actions/tests/test_transcript.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import transcript  # noqa: E402

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
                 "input": {"skill": "izg-benchmark-actions"}},
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
    # 4: Subagent-Block (isSidechain)
    {
        "type": "assistant", "timestamp": "2026-08-14T10:00:03Z", "requestId": "r2",
        "isSidechain": True,
        "message": {
            "usage": {"input_tokens": 30, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 15},
            "content": [],
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
    # 7: tool_result ohne passenden tool_use, content als dict
    {
        "type": "user", "timestamp": "2026-08-14T10:00:06Z",
        "message": {"content": [{"type": "tool_result", "tool_use_id": "orphan",
                                 "content": {"a": 1}}]},
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
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


class ReadSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sess-1.jsonl"
        write_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fehlende_datei_wirft_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            transcript.read_session(self.path.parent / "nope.jsonl", "sess-1")

    def test_requestid_entdopplung_ignoriert_zweiten_eintrag(self):
        su = transcript.read_session(self.path, "sess-1")
        # r1, u1, r2 - der doppelte r1-Eintrag zaehlt nicht mit
        self.assertEqual(su.requests, 3)

    def test_usage_summe_ueber_alle_requests(self):
        su = transcript.read_session(self.path, "sess-1")
        self.assertEqual(su.usage["input"], 100 + 50 + 30)
        self.assertEqual(su.usage["cache_read"], 10)
        self.assertEqual(su.usage["cache_creation"], 5)
        self.assertEqual(su.usage["output"], 20 + 10 + 15)

    def test_uuid_fallback_wird_gezaehlt(self):
        su = transcript.read_session(self.path, "sess-1")
        self.assertIn("Read", su.tool_calls)
        self.assertEqual(su.tool_calls["Read"], 1)

    def test_sidechain_output_getrennt_verbucht(self):
        su = transcript.read_session(self.path, "sess-1")
        self.assertEqual(su.subagent_output_tokens, 15)

    def test_skill_nutzung_erfasst(self):
        su = transcript.read_session(self.path, "sess-1")
        self.assertEqual(su.skills_used, {"izg-benchmark-actions": 1})

    def test_tool_result_ohne_passenden_tool_use_wird_stillschweigend_verworfen(self):
        su = transcript.read_session(self.path, "sess-1")
        # "orphan" gehoert zu keinem bekannten tool_use - taucht in keinem Tool auf,
        # darf aber auch keinen Fehler werfen (siehe setUp/Aufruf oben).
        self.assertNotIn("orphan", su.tool_result_tokens)

    def test_content_als_str_wird_gezaehlt(self):
        su = transcript.read_session(self.path, "sess-1")
        # "hello world" -> 11 Zeichen // CHARS_PER_TOKEN
        self.assertEqual(su.tool_result_tokens["Bash"], 11 // transcript.CHARS_PER_TOKEN)

    def test_content_als_list_wird_gezaehlt(self):
        su = transcript.read_session(self.path, "sess-1")
        expected_chars = len(json.dumps({"text": "yes"}, ensure_ascii=False))
        self.assertEqual(su.tool_result_tokens["Read"], expected_chars // transcript.CHARS_PER_TOKEN)

    def test_zeitstempel_spanne_ignoriert_kaputte_und_leere_zeilen(self):
        su = transcript.read_session(self.path, "sess-1")
        self.assertEqual(su.first_timestamp, "2026-08-14T10:00:00Z")
        self.assertEqual(su.last_timestamp, "2026-08-14T10:00:06Z")

    def test_session_id_wird_durchgereicht(self):
        su = transcript.read_session(self.path, "sess-1")
        self.assertEqual(su.session_id, "sess-1")


class TranscriptPath(unittest.TestCase):
    def test_projekt_slug_ersetzt_sonderzeichen(self):
        p = transcript.transcript_path(Path("/tmp/mein projekt"), "abc")
        self.assertTrue(str(p).endswith("abc.jsonl"))
        self.assertNotIn(" ", p.parent.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
