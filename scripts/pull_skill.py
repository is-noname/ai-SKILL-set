#!/usr/bin/env python3
"""Pulls skills and their transitive dependencies into a target project."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = REPO_ROOT / "registry.json"
SETS_DIR = REPO_ROOT / "skills" / "sets"

REQUIRES_FILENAME = "requires.json"
SETUP_FILENAME = "setup.sh"
REQUIRE_TYPES = ("cmd", "env", "py", "file")

# Verzeichnisse, die im Repo leben, aber nicht zum Skill gehören: generierte
# Artefakte und Messaufbauten (izg-benchmark-actions/benchmark/<task>/ hält die
# Messaufbauten für die gemessenen Skills — Repo-intern, nichts für ein Zielprojekt).
# Gilt für Pull UND Inhaltsvergleich — sonst
# gilt ein gepullter Skill dauerhaft als veraltet, weil ihm etwas fehlt, das er
# nie bekommen sollte.
IGNORE_DIR_NAMES = {"__pycache__", ".git", "benchmark"}
IGNORE_SUFFIXES = {".pyc", ".pyo", ".backup", ".db"}

# Lokale Secrets bleiben lokal: eine .env im Skill-Verzeichnis gehoert zur
# Maschine, nicht zum Skill. Sonst wandert z.B. der agentmail-API-Key in jedes
# Zielprojekt. Das Zielprojekt bekommt seine .env ueber setup.sh (requires.json).
# Gilt auch fuer den Digest — sonst gilt jede Installation als veraltet.
IGNORE_FILE_NAMES = {".env"}

REPO_ONLY = shutil.ignore_patterns(
    *IGNORE_DIR_NAMES, *IGNORE_FILE_NAMES, *(f"*{s}" for s in IGNORE_SUFFIXES)
)


def dir_digest(root: Path) -> str:
    """Stabiler Hash über alle relevanten Dateien eines Skill-Verzeichnisses.

    Erfasst Pfade UND Inhalte, damit auch Backend-Änderungen ohne SKILL.md-Änderung
    als veraltet erkannt werden. Generierte Artefakte (siehe IGNORE_*) bleiben außen vor.
    """
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if any(part in IGNORE_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        if path.suffix in IGNORE_SUFFIXES or path.name in IGNORE_FILE_NAMES:
            continue
        h.update(str(path.relative_to(root)).encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print("registry.json not found — run scripts/generate_registry.py first", file=sys.stderr)
        sys.exit(1)
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["skills"]


def load_set(set_name: str) -> list[str]:
    path = SETS_DIR / f"{set_name}.json"
    if not path.exists():
        print(f"Set '{set_name}' not found in {SETS_DIR}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["skills"]


def load_requires(skill_dir: Path) -> tuple[list[dict], list[str]]:
    """Liest requires.json eines Skills. Gibt (Anforderungen, Formatfehler) zurück.

    Fehlt die Datei, hat der Skill keine externen Voraussetzungen — das ist der
    Normalfall und kein Fehler.
    """
    path = skill_dir / REQUIRES_FILENAME
    if not path.exists():
        return [], []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"{path}: kein gültiges JSON ({exc})"]

    entries = data.get("requires", []) if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return [], [f"{path}: erwartet {{\"requires\": [...]}}"]

    valid: list[dict] = []
    errors: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{path}: Eintrag {i} ist kein Objekt")
            continue
        rtype = entry.get("type")
        value = entry.get("value")
        if rtype not in REQUIRE_TYPES:
            errors.append(f"{path}: Eintrag {i} hat unbekannten type '{rtype}' (erlaubt: {', '.join(REQUIRE_TYPES)})")
            continue
        if not isinstance(value, str) or not value:
            errors.append(f"{path}: Eintrag {i} ({rtype}) hat kein 'value'")
            continue
        valid.append(entry)
    return valid, errors


def _strip_quotes(value: str) -> str:
    """Entfernt ein umschließendes Anführungszeichen-Paar — wie env_loader.py der Skills."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_dotenv(path: Path) -> dict[str, str]:
    """Parst KEY=VALUE-Zeilen. Gleiche Semantik wie env_loader.py der Skills.

    Kommentare (`#`) und Zeilen ohne `=` werden übersprungen, `=` im Wert bleibt
    erhalten (nur am ersten `=` getrennt), ein umschließendes Quote-Paar fällt weg.
    Fehlt die Datei, ist das Ergebnis leer — kein Fehler.
    """
    if not path.is_file():
        return {}
    werte: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            werte[key] = _strip_quotes(value.strip())
    return werte


def _env_from_skill_dotenv(skill_dir: Path, var: str) -> str:
    """Wert von `var` aus der skill-eigenen .env ("" wenn nicht gesetzt).

    Nur `<skill>/.env` — genau die Datei, die `env_loader.py` der Skills liest.
    Projektwurzel, `.local`-Varianten oder übergeordnete Verzeichnisse werden
    bewusst ignoriert, sonst meldete die Prüfung grün, wo der Skill zur Laufzeit
    nichts findet.
    """
    return parse_dotenv(skill_dir / ".env").get(var, "")


def _is_placeholder(skill_dir: Path, var: str, value: str) -> bool:
    """True, wenn `value` unverändert aus `env.example.txt` stammt.

    Wer die Vorlage von Hand kopiert, hat `AGENTMAIL_INBOX=dein-agent@agentmail.to`
    stehen — nicht leer, aber auch nicht eingerichtet. Nur der Pfad über `setup.sh`
    leert die Platzhalter; der Handpfad ist der wahrscheinlichere.
    """
    vorlage = parse_dotenv(skill_dir / "env.example.txt").get(var, "")
    return bool(vorlage) and value == vorlage


def check_requirement(req: dict, skill_dir: Path) -> bool:
    rtype = req["type"]
    value = req["value"]

    if rtype == "cmd":
        return shutil.which(value) is not None
    if rtype == "env":
        # Nur Existenz, nie Gueltigkeit: ein rotierter oder falscher Key besteht
        # die Pruefung. Ein Netzwerkaufruf beim Pull waere der Preis dafuer.
        gesetzt = os.environ.get(value, "").strip() or _env_from_skill_dotenv(skill_dir, value)
        return bool(gesetzt) and not _is_placeholder(skill_dir, value, gesetzt)
    if rtype == "py":
        try:
            return importlib.util.find_spec(value) is not None
        except (ImportError, ValueError):
            return False
    if rtype == "file":
        return Path(os.path.expandvars(value)).expanduser().exists()
    return False


def check_skill(skill_dir: Path) -> tuple[list[dict], list[dict], list[str]]:
    """Gibt (fehlende Pflicht-, fehlende optionale Anforderungen, Formatfehler) zurück."""
    requires, errors = load_requires(skill_dir)
    missing: list[dict] = []
    missing_optional: list[dict] = []
    for req in requires:
        if check_requirement(req, skill_dir):
            continue
        # Platzhalter sind der Sonderfall, den "fehlt" falsch beschreibt: der
        # Wert steht da, nur eben unveraendert aus der Vorlage.
        if req["type"] == "env":
            wert = os.environ.get(req["value"], "").strip() or _env_from_skill_dotenv(
                skill_dir, req["value"]
            )
            if wert and _is_placeholder(skill_dir, req["value"], wert):
                req = {**req, "_grund": f"steht noch auf dem Platzhalter '{wert}'"}
        (missing_optional if req.get("optional") else missing).append(req)
    return missing, missing_optional, errors


def _format_req(req: dict) -> str:
    label = {
        "cmd": "Kommando",
        "env": "Umgebungsvariable",
        "py": "Python-Paket",
        "file": "Datei/Pfad",
    }[req["type"]]
    line = f"{label} '{req['value']}'"
    grund = req.get("_grund")
    if grund:
        line = f"{line} ({grund})"
    hint = req.get("hint")
    return f"{line} — {hint}" if hint else line


def report_requirements(names: list[str], skill_dir_for: dict, run_setup: bool = False) -> bool:
    """Prüft die Skills und gibt einen Bericht aus. True, wenn alles erfüllt ist."""
    all_ok = True

    for name in names:
        skill_dir = skill_dir_for[name]
        missing, missing_optional, errors = check_skill(skill_dir)
        setup = skill_dir / SETUP_FILENAME

        for err in errors:
            print(f"  ! {err}", file=sys.stderr)
            all_ok = False

        # Erst reparieren, dann urteilen — sonst gilt ein durch setup.sh
        # repariertes Skill weiterhin als unbrauchbar.
        if missing and run_setup and setup.exists():
            # flush: sonst landet die Ausgabe des Subprozesses vor dieser Zeile
            print(f"\n{name}: führe {SETUP_FILENAME} aus", flush=True)
            result = subprocess.run(["bash", str(setup)], cwd=str(skill_dir))
            if result.returncode != 0:
                print(f"  ! {SETUP_FILENAME} endete mit Code {result.returncode}", file=sys.stderr)
            missing, missing_optional, _ = check_skill(skill_dir)
            if not missing:
                print(f"  ✓ {name}: Voraussetzungen erfüllt")

        if not missing and not missing_optional:
            continue

        print(f"\n{name}: externe Voraussetzungen nicht erfüllt")
        for req in missing:
            print(f"  ✗ {_format_req(req)}")
        for req in missing_optional:
            print(f"  ~ {_format_req(req)} (optional)")

        if missing:
            all_ok = False
            if setup.exists():
                print(f"  → Setup vorhanden: bash {setup}")
                if not run_setup:
                    print("    (oder Pull/doctor mit --setup wiederholen)")

    return all_ok


def resolve(names: list[str], registry: dict) -> list[str]:
    """Returns skill names in topological install order (deps first)."""
    resolved: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name not in registry:
            print(f"Unknown skill: '{name}'", file=sys.stderr)
            sys.exit(1)
        visited.add(name)
        for dep in registry[name].get("dependencies", []):
            visit(dep)
        resolved.append(name)

    for name in names:
        visit(name)
    return resolved


def pull(
    names: list[str],
    target: Path,
    registry: dict,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[list[str], list[str]]:
    order = resolve(names, registry)
    installed: list[str] = []
    skipped: list[str] = []

    for name in order:
        src = REPO_ROOT / registry[name]["path"]
        dst = target / name

        if dst.exists() and not force:
            skipped.append(name)
            continue

        if not dry_run:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=REPO_ONLY)
        installed.append(name)

    return installed, skipped


def cmd_pull(args: argparse.Namespace, registry: dict) -> int:
    names: list[str] = list(args.skills)
    if args.set:
        names = load_set(args.set)

    if not names:
        print("No skills specified. Use skill names or --set <name>.", file=sys.stderr)
        return 1

    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)

    installed, skipped = pull(names, target, registry, dry_run=args.dry_run, force=args.force)

    if args.dry_run:
        print("[dry-run] would install:", ", ".join(installed) or "(none)")
        print("[dry-run] would skip (already present):", ", ".join(skipped) or "(none)")
        return 0

    if installed:
        print("Installed:", ", ".join(installed))
    if skipped:
        print("Skipped (already present, use --force to overwrite):", ", ".join(skipped))
    if not installed and not skipped:
        print("Nothing to do.")
        return 0

    # Auch die übersprungenen prüfen: "schon da" heißt nicht "einsatzbereit".
    touched = installed + skipped
    ok = report_requirements(touched, {n: target / n for n in touched}, run_setup=args.setup)

    # Die Dateien liegen zwar, aber der Skill ist nicht lauffähig — das muss ein
    # aufrufendes Script merken können, ohne die Ausgabe zu parsen.
    return 0 if ok else 1


def cmd_update(args: argparse.Namespace, registry: dict) -> int:
    target = Path(args.target)
    if not target.exists():
        print(f"Target '{target}' does not exist — nothing installed.", file=sys.stderr)
        return 1

    installed = [d.name for d in target.iterdir() if d.is_dir()]
    if not installed:
        print("No skills installed.")
        return 0

    outdated: list[str] = []
    unknown: list[str] = []

    for name in sorted(installed):
        if name not in registry:
            unknown.append(name)
            continue
        local_dir = target / name
        repo_dir = REPO_ROOT / registry[name]["path"]
        if not local_dir.exists() or not repo_dir.exists():
            outdated.append(name)
        elif dir_digest(local_dir) != dir_digest(repo_dir):
            outdated.append(name)

    if unknown:
        print("Unknown (not in registry, skipped):", ", ".join(unknown))

    if not outdated:
        print("All skills up to date.")
        return 0

    print("Outdated:", ", ".join(outdated))

    if args.dry_run:
        return 0

    installed_names, _ = pull(outdated, target, registry, force=True)
    print("Updated:", ", ".join(installed_names))

    # Ein Update kann neue Voraussetzungen mitbringen — direkt melden statt zur Laufzeit.
    ok = report_requirements(installed_names, {n: target / n for n in installed_names})
    return 0 if ok else 1


def cmd_doctor(args: argparse.Namespace, registry: dict) -> int:
    target = Path(args.target)
    if not target.exists():
        print(f"Target '{target}' does not exist — nothing installed.", file=sys.stderr)
        return 1

    installed = sorted(d.name for d in target.iterdir() if d.is_dir())
    if not installed:
        print("No skills installed.")
        return 0

    with_requires = [n for n in installed if (target / n / REQUIRES_FILENAME).exists()]
    if not with_requires:
        print(f"{len(installed)} Skills installiert, keiner deklariert externe Voraussetzungen.")
        return 0

    print(f"Prüfe {len(with_requires)} von {len(installed)} Skills mit externen Voraussetzungen...")
    ok = report_requirements(with_requires, {n: target / n for n in with_requires}, run_setup=args.setup)

    if ok:
        print("\nAlle externen Voraussetzungen erfüllt.")
        return 0
    return 1


def cmd_list(registry: dict) -> int:
    by_layer: dict[int, list] = {}
    for entry in registry.values():
        layer = entry.get("layer") if entry.get("layer") is not None else -1
        by_layer.setdefault(layer, []).append(entry)

    for layer in sorted(by_layer):
        print(f"\nLayer {layer}:")
        for entry in sorted(by_layer[layer], key=lambda e: e["name"]):
            deps = ", ".join(entry["dependencies"]) if entry["dependencies"] else "—"
            print(f"  {entry['name']:<30} {entry['description'][:60]}")
            if entry["dependencies"]:
                print(f"  {'':30} deps: {deps}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull skills from ai-SKILL-set into a project.")
    sub = parser.add_subparsers(dest="cmd")

    p_pull = sub.add_parser("pull", help="Pull skills into target directory")
    p_pull.add_argument("skills", nargs="*", metavar="SKILL", help="Skill names to pull")
    p_pull.add_argument("--set", metavar="NAME", help="Pull a predefined skill set")
    p_pull.add_argument(
        "--target",
        default=".claude/skills",
        metavar="DIR",
        help="Target directory (default: .claude/skills)",
    )
    p_pull.add_argument("--force", action="store_true", help="Overwrite already-installed skills")
    p_pull.add_argument("--dry-run", action="store_true", help="Show what would be installed")
    p_pull.add_argument(
        "--setup",
        action="store_true",
        help="Run a skill's setup.sh when its external requirements are unmet",
    )

    p_list = sub.add_parser("list", help="List available skills")

    p_doctor = sub.add_parser("doctor", help="Check external requirements of installed skills")
    p_doctor.add_argument(
        "--target",
        default=".claude/skills",
        metavar="DIR",
        help="Target directory (default: .claude/skills)",
    )
    p_doctor.add_argument(
        "--setup",
        action="store_true",
        help="Run a skill's setup.sh when its external requirements are unmet",
    )

    p_update = sub.add_parser("update", help="Update outdated installed skills")
    p_update.add_argument(
        "--target",
        default=".claude/skills",
        metavar="DIR",
        help="Target directory (default: .claude/skills)",
    )
    p_update.add_argument("--dry-run", action="store_true", help="Show what would be updated")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1

    registry = load_registry()

    if args.cmd == "pull":
        return cmd_pull(args, registry)
    if args.cmd == "list":
        return cmd_list(registry)
    if args.cmd == "update":
        return cmd_update(args, registry)
    if args.cmd == "doctor":
        return cmd_doctor(args, registry)
    return 1


if __name__ == "__main__":
    sys.exit(main())
