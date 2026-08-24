#!/usr/bin/env python3
"""Tests fuer kissd_lint — jeder Check bekommt einen positiven und einen negativen Fall."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "kissd_lint.py"
spec = importlib.util.spec_from_file_location("_izg_kissd_lint", SCRIPT)
lint = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lint
spec.loader.exec_module(lint)


CLEAN_SKILL = """---
name: demo
description: Tut etwas. Use when der Nutzer X will.
layer: 1
dependencies: []
---

# Demo

## Ablauf

1. Report erzeugen:

```bash
REPO=~/Dokumente/AI/ai-SKILL-set
python3 "$REPO/scripts/demo.py" --out report.md
```

## Verifikation

Erwartete Ausgabe: `report.md geschrieben`.

## Wenn etwas fehlschlaegt

Exit-Code 2 heisst: Pfad fehlt. Dann den Nutzer nach dem Repo-Pfad fragen.
"""


def write(tmp_path: Path, text: str, name: str = "demo") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    path = skill_dir / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    (skill_dir / "requires.json").write_text('{"requires": []}', encoding="utf-8")
    return path


def checks(findings) -> set[str]:
    return {f.check for f in findings}


def test_sauberer_skill_ohne_befunde(tmp_path):
    assert lint.audit_file(write(tmp_path, CLEAN_SKILL)) == []


def test_k10_fehlendes_frontmatter_blockt(tmp_path):
    findings = lint.audit_file(write(tmp_path, "# Ohne Frontmatter\n"))
    assert any(f.check == "K10" and f.severity == "block" for f in findings)


def test_k10_fehlendes_layer_ist_nur_warn(tmp_path):
    text = CLEAN_SKILL.replace("layer: 1\n", "")
    findings = [f for f in lint.audit_file(write(tmp_path, text)) if f.check == "K10"]
    assert [f.severity for f in findings] == ["warn"]


def test_k10_fehlende_description_blockt(tmp_path):
    text = "\n".join(l for l in CLEAN_SKILL.splitlines() if not l.startswith("description:"))
    findings = lint.audit_file(write(tmp_path, text))
    assert any(f.severity == "block" and "description" in f.message for f in findings)


def test_k10_name_muss_zum_verzeichnis_passen(tmp_path):
    text = CLEAN_SKILL.replace("name: demo", "name: anders")
    findings = lint.audit_file(write(tmp_path, text))
    assert any("!= Verzeichnis" in f.message for f in findings)


def test_k10_description_ohne_ausloeser(tmp_path):
    text = CLEAN_SKILL.replace("Use when der Nutzer X will.", "Macht Sachen.")
    assert "K10" in checks(lint.audit_file(write(tmp_path, text)))


def test_k1_vages_wort_in_prosa(tmp_path):
    text = CLEAN_SKILL.replace("# Demo", "# Demo\n\nDen passenden Pfad waehlen.")
    assert "K1" in checks(lint.audit_file(write(tmp_path, text)))


def test_k1_ignoriert_codebloecke(tmp_path):
    text = CLEAN_SKILL.replace('--out report.md', '--out report.md  # etc.')
    assert "K1" not in checks(lint.audit_file(write(tmp_path, text)))


def test_k1_ignoriert_zitiertes_negativbeispiel(tmp_path):
    text = CLEAN_SKILL.replace("# Demo", '# Demo\n\nFehlerbild: "den passenden Pfad waehlen".')
    assert "K1" not in checks(lint.audit_file(write(tmp_path, text)))


def test_k3_ignoriert_nicht_shell_fences(tmp_path):
    text = CLEAN_SKILL + "\n```markdown\n# Report: <ziel>\n```\n"
    assert "K3" not in checks(lint.audit_file(write(tmp_path, text)))


def test_k3_greift_in_unbenanntem_fence(tmp_path):
    text = CLEAN_SKILL + "\n```\nbash /pfad/setup.sh\n```\n"
    assert "K3" in checks(lint.audit_file(write(tmp_path, text)))


def test_k7_ignoriert_nicht_shell_fences(tmp_path):
    path = write(tmp_path, CLEAN_SKILL + "\n```json\nnpm install\n```\n", name="k7b")
    (path.parent / "requires.json").unlink()
    assert not any(f.check == "K7" and "npm" in f.message for f in lint.audit_file(path))


def test_k2_aufforderung_ohne_kopiervorlage(tmp_path):
    text = CLEAN_SKILL.replace("# Demo", "# Demo\n\nDas Setup ausführen und warten.")
    assert "K2" in checks(lint.audit_file(write(tmp_path, text)))


def test_k3_platzhalter_im_befehl(tmp_path):
    text = CLEAN_SKILL.replace("--out report.md", "--out /pfad/report.md")
    assert "K3" in checks(lint.audit_file(write(tmp_path, text)))


def test_k3_relativer_aufruf(tmp_path):
    text = CLEAN_SKILL.replace('python3 "$REPO/scripts/demo.py" --out report.md',
                               "./scripts/demo.py --out report.md")
    assert "K3" in checks(lint.audit_file(write(tmp_path, text)))


def test_k8_ungefiltertes_find(tmp_path):
    text = CLEAN_SKILL.replace('python3 "$REPO/scripts/demo.py" --out report.md',
                               "find . -type f")
    assert "K8" in checks(lint.audit_file(write(tmp_path, text)))


def test_k8_gefiltertes_find_ist_ok(tmp_path):
    text = CLEAN_SKILL.replace('python3 "$REPO/scripts/demo.py" --out report.md',
                               "find . -name '*.md' -maxdepth 2")
    assert "K8" not in checks(lint.audit_file(write(tmp_path, text)))


def test_k9_mkdir_ohne_p(tmp_path):
    text = CLEAN_SKILL.replace('python3 "$REPO/scripts/demo.py" --out report.md',
                               "mkdir out")
    assert "K9" in checks(lint.audit_file(write(tmp_path, text)))


def test_k4_und_k5_fehlen(tmp_path):
    text = CLEAN_SKILL.split("## Verifikation")[0]
    assert {"K4", "K5"} <= checks(lint.audit_file(write(tmp_path, text)))


def test_k6_ohne_nummerierung(tmp_path):
    text = CLEAN_SKILL.replace("1. Report erzeugen:", "Report erzeugen:")
    assert "K6" in checks(lint.audit_file(write(tmp_path, text)))


def test_k7_ohne_requires_json(tmp_path):
    path = write(tmp_path, CLEAN_SKILL, name="k7")
    (path.parent / "requires.json").unlink()
    findings = lint.audit_file(path)
    assert any(f.check == "K7" and "python3" in f.message for f in findings)


def test_k8_groesse(tmp_path):
    text = CLEAN_SKILL + "\nFuelltext.\n" * 1500
    assert any("Tokens" in f.message for f in lint.audit_file(write(tmp_path, text)))


def test_score_ist_deterministisch(tmp_path):
    path = write(tmp_path, "# leer\n")
    assert lint.score(lint.audit_file(path)) == lint.score(lint.audit_file(path))


def test_score_bodenwert_null(tmp_path):
    findings = [lint.Finding("K1", "block", "x", 1, "m", "f")] * 20
    assert lint.score(findings) == 0


def test_collect_targets_skill_ordner(tmp_path):
    path = write(tmp_path, CLEAN_SKILL)
    assert lint.collect_targets(str(path.parent)) == [path]


def test_collect_targets_baum(tmp_path):
    write(tmp_path, CLEAN_SKILL, name="a")
    write(tmp_path, CLEAN_SKILL, name="b")
    assert len(lint.collect_targets(str(tmp_path))) == 2


def test_collect_targets_fehlender_pfad(tmp_path):
    with pytest.raises(FileNotFoundError):
        lint.collect_targets(str(tmp_path / "gibtsnicht"))


def test_exit_code_block(tmp_path, capsys):
    path = write(tmp_path, "# ohne frontmatter\n")
    assert lint.main([str(path)]) == 1


def test_exit_code_strict_bei_warn(tmp_path):
    text = CLEAN_SKILL.replace("# Demo", "# Demo\n\nDen passenden Wert waehlen.")
    path = write(tmp_path, text)
    assert lint.main([str(path)]) == 0
    assert lint.main([str(path), "--strict"]) == 1


def test_exit_code_sauber(tmp_path):
    assert lint.main([str(write(tmp_path, CLEAN_SKILL))]) == 0


def test_json_ausgabe(tmp_path, capsys):
    lint.main([str(write(tmp_path, CLEAN_SKILL)), "--json"])
    import json
    data = json.loads(capsys.readouterr().out)
    assert data["score"] == 100 and data["findings"] == []


def test_report_zweimal_identisch(tmp_path):
    path = write(tmp_path, "# leer\n")
    first = lint.render(sorted(lint.audit_file(path), key=lambda f: (f.check, f.line)), [path])
    second = lint.render(sorted(lint.audit_file(path), key=lambda f: (f.check, f.line)), [path])
    assert first == second
