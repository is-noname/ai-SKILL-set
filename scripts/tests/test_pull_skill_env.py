"""Tests fuer die env-Pruefung aus requires.json (IZG-T-157).

Der Parser sieht harmlos aus, ist aber die Stelle, an der ein stiller Fehler
niemandem auffaellt: doctor meldet gruen, der Skill findet zur Laufzeit nichts.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pull_skill import (  # noqa: E402
    _env_from_skill_dotenv,
    _is_placeholder,
    check_requirement,
    check_skill,
    parse_dotenv,
)


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    return tmp_path


def schreibe(pfad: Path, inhalt: str) -> None:
    pfad.write_text(inhalt, encoding="utf-8")


# --- parse_dotenv / _env_from_skill_dotenv ---------------------------------


def test_fehlende_datei_ist_kein_fehler(skill_dir: Path):
    assert parse_dotenv(skill_dir / ".env") == {}
    assert _env_from_skill_dotenv(skill_dir, "IRGENDWAS") == ""


def test_kommentare_und_leerzeilen_werden_uebersprungen(skill_dir: Path):
    schreibe(skill_dir / ".env", "# Kommentar\n\n#KEY=aus-kommentar\nKEY=echt\n")
    assert parse_dotenv(skill_dir / ".env") == {"KEY": "echt"}


def test_quotes_werden_entfernt(skill_dir: Path):
    schreibe(skill_dir / ".env", "A=\"mit spaces\"\nB='einfach'\nC=roh\n")
    werte = parse_dotenv(skill_dir / ".env")
    assert werte == {"A": "mit spaces", "B": "einfach", "C": "roh"}


def test_unpaarige_quotes_bleiben_stehen(skill_dir: Path):
    schreibe(skill_dir / ".env", "A=\"halb\n")
    assert parse_dotenv(skill_dir / ".env")["A"] == '"halb'


def test_gleichheitszeichen_im_wert_bleibt_erhalten(skill_dir: Path):
    schreibe(skill_dir / ".env", "KEY=abc=def==\n")
    assert parse_dotenv(skill_dir / ".env")["KEY"] == "abc=def=="


def test_leerer_wert_gilt_als_nicht_gesetzt(skill_dir: Path):
    schreibe(skill_dir / ".env", "KEY=\nSPACES=   \n")
    assert _env_from_skill_dotenv(skill_dir, "KEY") == ""
    assert _env_from_skill_dotenv(skill_dir, "SPACES") == ""


def test_zeile_ohne_gleichheitszeichen_wird_ignoriert(skill_dir: Path):
    schreibe(skill_dir / ".env", "kaputt\nKEY=ok\n")
    assert parse_dotenv(skill_dir / ".env") == {"KEY": "ok"}


def test_kaputte_bytes_lassen_den_rest_intakt(skill_dir: Path):
    (skill_dir / ".env").write_bytes(b"KEY=\xff\xfe\nZWEI=ok\n")
    assert parse_dotenv(skill_dir / ".env")["ZWEI"] == "ok"


# --- Platzhalter ------------------------------------------------------------


def test_platzhalter_aus_vorlage_gilt_nicht_als_gesetzt(skill_dir: Path):
    schreibe(skill_dir / "env.example.txt", "INBOX=dein-agent@agentmail.to\n")
    schreibe(skill_dir / ".env", "INBOX=dein-agent@agentmail.to\n")
    assert _is_placeholder(skill_dir, "INBOX", "dein-agent@agentmail.to")
    assert not check_requirement({"type": "env", "value": "INBOX"}, skill_dir)


def test_echter_wert_besteht_trotz_vorlage(skill_dir: Path):
    schreibe(skill_dir / "env.example.txt", "INBOX=dein-agent@agentmail.to\n")
    schreibe(skill_dir / ".env", "INBOX=echt@agentmail.to\n")
    assert check_requirement({"type": "env", "value": "INBOX"}, skill_dir)


def test_leerer_vorlagenwert_macht_keinen_platzhalter(skill_dir: Path):
    # env.example.txt mit `KEY=` darf nicht dazu fuehren, dass jeder leere Wert
    # als "Platzhalter" gilt — leer ist ohnehin schon nicht erfuellt.
    schreibe(skill_dir / "env.example.txt", "KEY=\n")
    assert not _is_placeholder(skill_dir, "KEY", "irgendwas")


def test_platzhalter_auch_aus_der_shell(skill_dir: Path, monkeypatch):
    schreibe(skill_dir / "env.example.txt", "KEY=whsec_...\n")
    monkeypatch.setenv("KEY", "whsec_...")
    assert not check_requirement({"type": "env", "value": "KEY"}, skill_dir)


def test_fehlende_vorlage_laesst_jeden_wert_gelten(skill_dir: Path):
    schreibe(skill_dir / ".env", "KEY=x\n")
    assert check_requirement({"type": "env", "value": "KEY"}, skill_dir)


# --- Fundorte ---------------------------------------------------------------


def test_shell_variable_reicht(skill_dir: Path, monkeypatch):
    monkeypatch.setenv("NUR_SHELL", "wert")
    assert check_requirement({"type": "env", "value": "NUR_SHELL"}, skill_dir)


def test_env_ausserhalb_des_skills_zaehlt_nicht(skill_dir: Path):
    # env_loader.py der Skills liest ausschliesslich <skill>/.env — eine .env
    # daneben oder eine Ebene hoeher wuerde zur Laufzeit nicht gefunden.
    unter = skill_dir / "skill"
    unter.mkdir()
    schreibe(skill_dir / ".env", "KEY=wert\n")
    schreibe(unter / ".env.local", "KEY=wert\n")
    assert not check_requirement({"type": "env", "value": "KEY"}, unter)


# --- Report -----------------------------------------------------------------


def test_check_skill_nennt_den_platzhalter_als_grund(skill_dir: Path):
    schreibe(skill_dir / "env.example.txt", "INBOX=dein-agent@agentmail.to\n")
    schreibe(skill_dir / ".env", "INBOX=dein-agent@agentmail.to\n")
    schreibe(
        skill_dir / "requires.json",
        '{"requires": [{"type": "env", "value": "INBOX"}]}',
    )
    missing, _, errors = check_skill(skill_dir)
    assert errors == []
    assert len(missing) == 1
    assert "Platzhalter" in missing[0]["_grund"]
