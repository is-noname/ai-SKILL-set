#!/usr/bin/env python3
"""Tests fuer render.py - stdlib only (kein pytest noetig).

    python3 tests/test_render.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analyze_transcript as at  # noqa: E402
from render import render_html  # noqa: E402


def make_data(**overrides) -> dict:
    data = at.empty_data()
    data.update({
        "sessions": 3,
        "requests": 12,
        "cache_hit_rate": 0.90,
        "tokens_per_tool": {"Bash": 400, "Read": 100},
        "repeats": [
            {"tool": "Bash", "label": "ls", "count": 4, "tokens": 200},
            {"tool": "Read", "label": "x.py", "count": 3, "tokens": 90},
        ],
    })
    data.update(overrides)
    return data


class RenderHtml(unittest.TestCase):
    def test_ein_balken_je_tool(self):
        html = render_html(make_data(), "demo", "2026-08-14")
        self.assertEqual(html.count('class="bar burn"'), 2)

    def test_eine_zeile_je_repeat(self):
        html = render_html(make_data(), "demo", "2026-08-14")
        self.assertEqual(html.count("<tr>"), 2)  # nur die tbody-Zeilen, thead nutzt eine eigene Klasse

    def test_cache_kachel_rot_unter_schwelle(self):
        html = render_html(make_data(cache_hit_rate=0.80), "demo", "2026-08-14")
        self.assertIn("bg-red-50", html)

    def test_cache_kachel_nicht_rot_ueber_schwelle(self):
        html = render_html(make_data(cache_hit_rate=0.90), "demo", "2026-08-14")
        self.assertNotIn("bg-red-50", html)

    def test_leerfall_zeigt_roten_kasten(self):
        html = render_html(at.empty_data(), "demo", "2026-08-14")
        self.assertIn("Keine Messdaten", html)

    def test_leerfall_keine_balken(self):
        html = render_html(at.empty_data(), "demo", "2026-08-14")
        self.assertEqual(html.count('class="bar burn"'), 0)

    def test_kandidaten_und_hebel_container_vorhanden_und_leer(self):
        html = render_html(make_data(), "demo", "2026-08-14")
        self.assertIn('<section id="kandidaten" class="space-y-10"></section>', html)
        self.assertIn('<section id="hebel"></section>', html)

    def test_projektname_und_datum_im_header(self):
        html = render_html(make_data(), "mein-projekt", "2026-08-14 09:00")
        self.assertIn("mein-projekt", html)
        self.assertIn("2026-08-14 09:00", html)

    def test_tool_und_label_werden_escaped(self):
        data = make_data(tokens_per_tool={"<img onerror=x>": 10})
        html = render_html(data, "demo", "2026-08-14")
        self.assertIn("&lt;img onerror=x&gt;", html)
        self.assertNotIn("<img onerror=x>", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
