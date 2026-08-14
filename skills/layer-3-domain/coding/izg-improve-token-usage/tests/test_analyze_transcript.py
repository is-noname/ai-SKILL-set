#!/usr/bin/env python3
"""Tests fuer analyze_transcript.py - stdlib only (kein pytest noetig).

Baut eine Fixture-JSONL von Hand und ruft find_transcripts()/analyze() ueber
einen expliziten base_dir auf - kein HOME-Zugriff, keine echte
Claude-Code-Installation noetig. Vorlage:
izg-benchmark-actions/tests/test_transcript.py.

    python3 tests/test_analyze_transcript.py
    python3 -m unittest discover skills/layer-3-domain/coding/izg-improve-token-usage/tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analyze_transcript as at  # noqa: E402

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
                 "input": {"skill": "izg-improve-token-usage"}},
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
        files = at.find_transcripts(Path("/nicht/vorhanden"), None,
                                     base_dir=self.base / "nope")
        self.assertEqual(files, [])

    def test_base_dir_wird_statt_home_verwendet(self):
        files = at.find_transcripts(Path("egal"), None, base_dir=self.base)
        self.assertEqual({f.name for f in files}, {"sess-1.jsonl", "sess-2.jsonl"})

    def test_session_filtert_auf_eine_datei(self):
        files = at.find_transcripts(Path("egal"), None, "sess-1", base_dir=self.base)
        self.assertEqual([f.name for f in files], ["sess-1.jsonl"])

    def test_session_ohne_treffer_liefert_leere_liste(self):
        files = at.find_transcripts(Path("egal"), None, "sess-nope", base_dir=self.base)
        self.assertEqual(files, [])

    def test_limit_begrenzt_anzahl(self):
        files = at.find_transcripts(Path("egal"), 1, base_dir=self.base)
        self.assertEqual(len(files), 1)


class Analyze(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sess-1.jsonl"
        write_fixture(self.path)
        self.data = at.analyze([self.path])

    def tearDown(self):
        self.tmp.cleanup()

    def test_requestid_entdopplung_ignoriert_zweiten_eintrag(self):
        # r1, u1, r2 - der doppelte r1-Eintrag zaehlt nicht mit
        self.assertEqual(self.data["requests"], 3)

    def test_usage_summe_ueber_alle_requests(self):
        t = self.data["totals"]
        self.assertEqual(t["input"], 100 + 50 + 30)
        self.assertEqual(t["cache_read"], 10)
        self.assertEqual(t["cache_creation"], 5)
        self.assertEqual(t["output"], 20 + 10 + 15)

    def test_uuid_fallback_wird_gezaehlt(self):
        self.assertEqual(self.data["calls_per_tool"].get("Read"), 1)

    def test_sidechain_output_getrennt_verbucht(self):
        self.assertEqual(self.data["subagent_output_tokens"], 15)

    def test_skill_nutzung_erfasst(self):
        self.assertEqual(self.data["skills_used"], {"izg-improve-token-usage": 1})

    def test_tool_result_ohne_passenden_tool_use_wird_stillschweigend_verworfen(self):
        # "orphan" gehoert zu keinem bekannten tool_use - darf keinen Fehler werfen
        # und darf in keinem der gezaehlten Tokens auftauchen.
        tokens_gesamt = sum(self.data["tokens_per_tool"].values())
        erwartet = (11 // at.CHARS_PER_TOKEN
                    + len(json.dumps({"text": "yes"}, ensure_ascii=False)) // at.CHARS_PER_TOKEN
                    + len(json.dumps({"a": 1}, ensure_ascii=False)) // at.CHARS_PER_TOKEN)
        self.assertEqual(tokens_gesamt, erwartet)

    def test_content_als_str_wird_gezaehlt(self):
        # t1 (Bash, "hello world") und t4 (Bash, gleicher Aufruf) zusammen
        bash_call = next(c for c in self.data["top_calls"] if c["label"] == "ls")
        self.assertIsNotNone(bash_call)

    def test_content_als_list_wird_gezaehlt(self):
        read_tokens = self.data["tokens_per_tool"].get("Read")
        expected_chars = len(json.dumps({"text": "yes"}, ensure_ascii=False))
        self.assertEqual(read_tokens, expected_chars // at.CHARS_PER_TOKEN)

    def test_content_als_dict_wird_gezaehlt(self):
        # t4 ist sidechain, traegt aber trotzdem zu den Bash-Tokens bei
        bash_tokens = self.data["tokens_per_tool"].get("Bash")
        expected = 11 // at.CHARS_PER_TOKEN + len(json.dumps({"a": 1}, ensure_ascii=False)) // at.CHARS_PER_TOKEN
        self.assertEqual(bash_tokens, expected)

    def test_sidechain_aufruf_ist_als_solcher_markiert(self):
        sidechain_calls = [c for c in self.data["top_calls"] if c["sidechain"]]
        self.assertEqual(len(sidechain_calls), 1)
        self.assertEqual(sidechain_calls[0]["tool"], "Bash")

    def test_wiederholte_aufrufe_werden_ueber_call_label_gruppiert(self):
        # t1 und t4 sind beides Bash-Aufrufe mit command "ls" -> gleiches Label
        repeat = next((r for r in self.data["repeats"]
                       if r["tool"] == "Bash" and r["label"] == "ls"), None)
        self.assertIsNotNone(repeat)
        self.assertEqual(repeat["count"], 2)

    def test_analyze_liefert_findings_schluessel(self):
        self.assertIn("findings", self.data)
        self.assertIsInstance(self.data["findings"], list)

    def test_kaputte_und_leere_zeilen_werfen_keinen_fehler(self):
        # analyze() in setUp() ist bereits durch die Fixture mit "{not valid json"
        # und Leerzeilen gelaufen, ohne zu werfen - requests bleibt korrekt.
        self.assertEqual(self.data["requests"], 3)


class ComputeFindings(unittest.TestCase):
    """Regeltests ueber ein echtes Measurement aus analyze(fixture), kein Dict von Hand."""

    def measurement(self, entries: list[dict]) -> at.Measurement:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sess-1.jsonl"
            path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
                             encoding="utf-8")
            data = at.analyze([path])
        data = dict(data)
        data["findings"] = []
        return at.Measurement(**data)

    def entry(self, req_id: str, input_=0, cache_read=0, cache_creation=0, output=0, tool_uses=()):
        return {
            "type": "assistant", "timestamp": "2026-08-14T10:00:00Z", "requestId": req_id,
            "message": {
                "usage": {"input_tokens": input_, "cache_read_input_tokens": cache_read,
                          "cache_creation_input_tokens": cache_creation, "output_tokens": output},
                "content": list(tool_uses),
            },
        }

    def test_cache_quote_unter_schwelle_erzeugt_ein_finding(self):
        m = self.measurement([self.entry("r1", input_=20, cache_read=80)])  # 80/100 = 0.80 < 0.85
        findings = at.compute_findings(m)
        cache_findings = [f for f in findings if f.signal == "cache-bruch"]
        self.assertEqual(len(cache_findings), 1)
        self.assertEqual(cache_findings[0].value, 0.80)

    def test_cache_quote_ueber_schwelle_erzeugt_kein_finding(self):
        m = self.measurement([self.entry("r1", input_=10, cache_read=90)])  # 90/100 = 0.90 >= 0.85
        findings = at.compute_findings(m)
        cache_findings = [f for f in findings if f.signal == "cache-bruch"]
        self.assertEqual(cache_findings, [])

    def test_ohne_usage_kein_cache_bruch_finding(self):
        m = self.measurement([self.entry("r1")])
        findings = at.compute_findings(m)
        self.assertEqual(findings, [])

    def test_redundanz_ab_schwelle_erzeugt_finding(self):
        tool_use = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "x.py"}}
        entries = [self.entry(f"r{i}", tool_uses=[tool_use])
                   for i in range(at.REDUNDANZ_COUNT_THRESHOLD)]
        m = self.measurement(entries)
        findings = at.compute_findings(m)
        redundanz = [f for f in findings if f.signal == "redundanz"]
        self.assertEqual(len(redundanz), 1)
        self.assertEqual(redundanz[0].value, at.REDUNDANZ_COUNT_THRESHOLD)

    def test_redundanz_unter_schwelle_kein_finding(self):
        tool_use = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "x.py"}}
        entries = [self.entry(f"r{i}", tool_uses=[tool_use])
                   for i in range(at.REDUNDANZ_COUNT_THRESHOLD - 1)]
        m = self.measurement(entries)
        findings = at.compute_findings(m)
        self.assertEqual([f for f in findings if f.signal == "redundanz"], [])


class ContentLen(unittest.TestCase):
    def test_str(self):
        self.assertEqual(at.content_len("abcd"), 4)

    def test_list_von_blocktexten(self):
        self.assertEqual(at.content_len(["ab", "cd"]), 4)

    def test_list_von_dict_bloecken(self):
        blocks = [{"content": "xy"}]
        self.assertEqual(at.content_len(blocks), len(json.dumps("xy", ensure_ascii=False)))

    def test_dict(self):
        self.assertEqual(at.content_len({"a": 1}), len(json.dumps({"a": 1}, ensure_ascii=False)))

    def test_sonstiges_liefert_null(self):
        self.assertEqual(at.content_len(None), 0)
        self.assertEqual(at.content_len(42), 0)


class CallLabel(unittest.TestCase):
    def test_read_edit_write_nutzen_file_path(self):
        self.assertEqual(at.call_label("Read", {"file_path": "/a/b.py"}), "/a/b.py")
        self.assertEqual(at.call_label("Write", {"file_path": "/a/c.py"}), "/a/c.py")

    def test_bash_kuerzt_und_ersetzt_newlines(self):
        label = at.call_label("Bash", {"command": "echo a\necho b"})
        self.assertEqual(label, "echo a echo b")

    def test_bash_kappt_bei_120_zeichen(self):
        label = at.call_label("Bash", {"command": "x" * 200})
        self.assertEqual(len(label), 120)

    def test_grep_glob_kombiniert_pattern_und_pfad(self):
        self.assertEqual(at.call_label("Grep", {"pattern": "foo", "path": "src"}), "foo @ src")

    def test_agent_kombiniert_typ_und_beschreibung(self):
        label = at.call_label("Agent", {"subagent_type": "general-purpose", "description": "such was"})
        self.assertEqual(label, "general-purpose: such was")

    def test_skill_nutzt_skillnamen(self):
        self.assertEqual(at.call_label("Skill", {"skill": "izg-domain-modeling"}), "izg-domain-modeling")

    def test_unbekanntes_tool_faellt_auf_json_zurueck(self):
        label = at.call_label("Sonstiges", {"x": 1})
        self.assertEqual(label, json.dumps({"x": 1}, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
