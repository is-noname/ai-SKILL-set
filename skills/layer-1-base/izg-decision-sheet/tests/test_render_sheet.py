#!/usr/bin/env python3
"""Tests fuer die Vorlagen-Auswahl in render_sheet.py - stdlib only (kein pytest noetig).

Geprueft wird choose_template als reine Auswahl ueber zwei Kandidaten: kein
Dateisystem, kein gefaelschtes Home-Verzeichnis. Genau dafuer ist die Funktion von
`local_copy()`/`shared_copy()` getrennt - die lesen, diese entscheidet.

    python3 -m unittest discover skills/layer-1-base/izg-decision-sheet/tests
    python3 skills/layer-1-base/izg-decision-sheet/tests/test_render_sheet.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import render_sheet  # noqa: E402

LOKAL = Path("/projekt/.claude/skills/izg-decision-sheet/assets/index.html")
SPIEGEL = Path("/home/u/ai-shared/izg-decision-sheet/index.html")


def copy(template: Path, **files: str) -> render_sheet.Copy:
    return render_sheet.Copy(template, dict(files))


class ChooseTemplate(unittest.TestCase):
    def test_nur_spiegel_hook_pfad(self):
        """Der Hook laeuft aus dem Spiegel - daneben liegt kein assets/."""
        template, note = render_sheet.choose_template(None, copy(SPIEGEL, index_html="a"))
        self.assertEqual(template, SPIEGEL)
        self.assertIsNone(note)

    def test_nur_lokal_ohne_globales_setup(self):
        template, note = render_sheet.choose_template(copy(LOKAL, index_html="a"), None)
        self.assertEqual(template, LOKAL)
        self.assertIsNone(note)

    def test_gar_nichts(self):
        with self.assertRaises(render_sheet.TemplateMissing):
            render_sheet.choose_template(None, None)

    def test_gleichstand_schweigt(self):
        beide = dict(index_html="a", sheet_state_py="b")
        template, note = render_sheet.choose_template(copy(LOKAL, **beide), copy(SPIEGEL, **beide))
        self.assertEqual(template, LOKAL)
        self.assertIsNone(note)

    def test_lokal_schlaegt_spiegel(self):
        """Frisch gepullter Skill gewinnt gegen alten Spiegel - und sagt es."""
        template, note = render_sheet.choose_template(
            copy(LOKAL, index_html="neu"), copy(SPIEGEL, index_html="alt")
        )
        self.assertEqual(template, LOKAL)
        self.assertIn("index_html", note)
        self.assertIn("setup_global_conventions.sh", note)

    def test_fehlende_datei_im_spiegel_zaehlt_als_abweichung(self):
        """Der Fall aus IZG-T-069: sheet_state.py fehlte im Spiegel, still."""
        _template, note = render_sheet.choose_template(
            copy(LOKAL, index_html="a", sheet_state_py="b"), copy(SPIEGEL, index_html="a")
        )
        self.assertIn("sheet_state_py", note)
        self.assertNotIn("index_html", note)

    def test_meldung_nennt_alle_abweichungen_sortiert(self):
        _template, note = render_sheet.choose_template(
            copy(LOKAL, index_html="a", render_sheet_py="x", sheet_spec_py="y"),
            copy(SPIEGEL, index_html="b", render_sheet_py="x", sheet_spec_py="z"),
        )
        self.assertIn("index_html, sheet_spec_py", note)


class Ablagen(unittest.TestCase):
    """Die lesenden Helfer - hier reicht, dass sie auf dem echten Skill aufgehen."""

    def test_local_copy_findet_die_kopie_neben_dem_script(self):
        local = render_sheet.local_copy()
        self.assertIsNotNone(local, "assets/index.html fehlt neben scripts/")
        self.assertEqual(set(local.files), set(render_sheet.MIRRORED))


if __name__ == "__main__":
    unittest.main()
