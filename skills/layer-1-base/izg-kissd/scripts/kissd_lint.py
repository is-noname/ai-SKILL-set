#!/usr/bin/env python3
"""KISSD-Lint: prueft Skills und Workflow-Dokumente auf Idiotensicherheit.

Der Lint deckt die mechanisch entscheidbaren Teile der KISSD-Rubrik ab (K1-K10).
Alles was Urteilsvermoegen braucht, bleibt bewusst im SKILL.md — hier steht nur,
was ein Regex zuverlaessig und reproduzierbar findet.

Zwei Regeln, die den Lint selbst idiotensicher halten:
- Die Ausgabe ist deterministisch sortiert (Datei, Check-ID, Zeile). Zwei Laeufe
  ueber denselben Stand liefern byte-identische Reports und lassen sich diffen.
- Exit-Code statt Prosa-Parsing: 1 bei `block`-Findings, mit --strict auch bei `warn`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# Frontmatter laut skills/README.md. Severity getrennt, weil die Folgen es sind:
# ohne name/description findet kein Modell den Skill (block); layer/dependencies
# inferiert generate_registry.py aus dem Pfad — der Pull laeuft, die Deklaration
# fehlt trotzdem (warn).
FIELD_SEVERITY = {
    "name": "block",
    "description": "block",
    "layer": "warn",
    "dependencies": "warn",
}

# Woerter, die dem Agenten die Entscheidung ueberlassen statt sie zu treffen
VAGUE_WORDS = [
    "geeignet", "passend", "sinnvoll", "angemessen", "gegebenenfalls", "ggf.",
    "eventuell", "bei bedarf", "nach bedarf", "moeglichst", "möglichst",
    "aehnlich", "ähnlich", "o.ae.", "o.ä.", "usw.", "etc.", "relevant",
    "appropriate", "suitable", "as needed", "if necessary", "as appropriate",
    "reasonable", "and so on", "or similar",
]

# Platzhalter in Codebloecken: der Agent muss raten, was einzusetzen ist
PLACEHOLDER_PATTERNS = [
    (r"<[a-zA-Z_äöüÄÖÜ][^>]{0,40}>", "Platzhalter <...>"),
    (r"/pfad/|/path/to/|DEIN_|MEIN_|YOUR_|TODO", "Platzhalter-Pfad/Token"),
    (r"\.\.\.", "Auslassung ..."),
]

# Kommandos, die Kontext ungefiltert ins Fenster kippen (K8)
TOKEN_WASTERS = [
    (r"\bcat\s+[^|]*$", "cat ohne Filter — Read mit offset/limit nutzen"),
    (r"\bls\s+-[a-zA-Z]*R", "ls -R — Glob nutzen oder eingrenzen"),
    (r"\bfind\s+", "find ohne -name/-maxdepth/Nachfilter"),
    (r"\bgrep\s+-[a-zA-Z]*r", "rekursives grep ohne Pfadgrenze"),
]
# Was ein find/grep entschaerft
FILTER_HINTS = ("-name", "-maxdepth", "| head", "|head", "| grep", "|grep", "| wc", "|wc")

# Shell-Builtins und Allerwelts-Tools brauchen keine requires.json
COMMON_CMDS = {
    "cd", "echo", "ls", "cat", "cp", "mv", "rm", "mkdir", "test", "for", "if",
    "then", "fi", "do", "done", "while", "export", "read", "set", "source",
    "sed", "awk", "grep", "head", "tail", "wc", "sort", "uniq", "cut", "tr",
    "true", "false", "exit", "printf", "touch", "chmod", "bash", "sh", "date",
}

# Formulierungen, die in der description den Ausloeser benennen. Deutsch gehoert
# dazu: die Skills dieses Repos schreiben ihn als "Dieser Skill sollte verwendet
# werden, wenn ..." — das ist ein Ausloeser, kein fehlender.
TRIGGER_MARKERS = (
    "use when", "use this", "verwenden wenn", "verwendet werden, wenn",
    "verwendet werden wenn", "genutzt werden, wenn", "genutzt werden wenn",
    "aufrufen, wenn", "einsetzen, wenn", "should be used when",
)

VERIFY_MARKERS = ("verif", "prüf", "pruef", "check", "erwartete ausgabe",
                  "erwartet:", "expected", "danach sollte", "test")
ERROR_MARKERS = ("fehler", "schlägt fehl", "schlaegt fehl", "fails", "failure",
                 "exit-code", "exit code", "wenn nicht", "falls nicht", "error")

SEVERITY_WEIGHT = {"block": 10, "warn": 3, "info": 1}
SEVERITY_ORDER = {"block": 0, "warn": 1, "info": 2}


@dataclass
class Finding:
    """Ein Befund. `fix` ist Pflicht — ein Befund ohne Vorschlag ist Rauschen."""

    check: str
    severity: str
    file: str
    line: int
    message: str
    fix: str


def split_frontmatter(text: str) -> tuple[dict, int]:
    """Zerlegt YAML-Frontmatter flach (nur `key: value`, kein YAML-Parser noetig).

    Returns:
        (Felder, Zeilennummer nach dem schliessenden ---). Leeres Dict wenn kein
        Frontmatter vorhanden.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fields: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return fields, i
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields, len(lines)


# Fence-Sprachen, deren Inhalt als auszufuehrender Befehl gilt. Eine ```markdown-
# Vorlage enthaelt Platzhalter mit Absicht — die darf kein K3-Befund werden.
SHELL_LANGS = {"", "bash", "sh", "shell", "zsh", "console", "shell-session"}


def iter_lines(text: str):
    """Liefert (zeilennummer, zeile, in_code, lang) — Codebloecke sauber getrennt.

    `lang` ist die Fence-Sprache in Kleinschreibung ("" wenn keine angegeben) und
    ausserhalb von Codebloecken None.
    """
    in_code = False
    lang: str | None = None
    for no, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if in_code:
                in_code, lang = False, None
            else:
                in_code, lang = True, stripped[3:].strip().lower()
            continue
        yield no, line, in_code, lang


def strip_quoted(line: str) -> str:
    """Entfernt zitierte Passagen — ein zitiertes Negativbeispiel ist keine Anweisung."""
    return re.sub(r"[\"'„»](.{0,120}?)[\"'“«]", " ", line)


def check_frontmatter(path: Path, text: str, is_skill: bool) -> list[Finding]:
    """K10 — Metadaten. Fehler hier machen den Skill unauffindbar oder unpullbar."""
    out: list[Finding] = []
    if not is_skill:
        return out
    fields, _ = split_frontmatter(text)
    if not fields:
        return [Finding("K10", "block", str(path), 1,
                        "Kein YAML-Frontmatter",
                        "Block mit name/description/layer/dependencies an den Dateianfang")]
    for field, severity in FIELD_SEVERITY.items():
        if field not in fields:
            out.append(Finding("K10", severity, str(path), 1,
                               f"Frontmatter-Feld '{field}' fehlt",
                               f"'{field}:' ergaenzen (siehe skills/README.md)"))
    name = fields.get("name", "")
    if name and name != path.parent.name:
        out.append(Finding("K10", "block", str(path), 1,
                           f"name '{name}' != Verzeichnis '{path.parent.name}'",
                           "Beide angleichen — der Pull matcht ueber den Namen"))
    desc = fields.get("description", "")
    if desc and not any(m in desc.lower() for m in TRIGGER_MARKERS):
        out.append(Finding("K10", "warn", str(path), 1,
                           "description nennt keinen Ausloeser ('Use when ...')",
                           "Satz anhaengen: 'Use when <konkreter Ausloeser>.'"))
    return out


def check_prose(path: Path, text: str) -> list[Finding]:
    """K1 vage Anweisungen, K2 Anweisung ohne Kopiervorlage."""
    out: list[Finding] = []
    lines = text.splitlines()
    for no, line, in_code, _ in iter_lines(text):
        if in_code:
            continue
        low = strip_quoted(line).lower()
        for word in VAGUE_WORDS:
            if word in low:
                out.append(Finding("K1", "warn", str(path), no,
                                   f"Vage Anweisung: '{word}'",
                                   "Durch die konkrete Bedingung oder den exakten Wert ersetzen"))
                break
        # Gross geschrieben ist es im Deutschen das substantivierte Verb ("zwei
        # Aufrufen mehr") — eine Feststellung, keine Anweisung. Deshalb wird hier
        # gegen die Originalschreibung geprueft, nicht gegen `low`.
        plain = strip_quoted(line)
        if re.search(r"\b(ausführen|ausfuehren|aufrufen|starten?|run|execute)\b", plain):
            if "`" not in line:
                window = "\n".join(lines[no:no + 3])
                if "```" not in window and "`" not in window:
                    out.append(Finding("K2", "warn", str(path), no,
                                       "Aufforderung ohne Kopiervorlage",
                                       "Exakten Befehl als Codeblock direkt darunter setzen"))
    return out


def check_code_blocks(path: Path, text: str) -> list[Finding]:
    """K3 Platzhalter/Pfade, K8 Token-Fresser, K9 Idempotenz."""
    out: list[Finding] = []
    for no, line, in_code, lang in iter_lines(text):
        if not in_code or lang not in SHELL_LANGS:
            continue
        if not line.strip() or line.strip().startswith("#"):
            continue
        for pattern, label in PLACEHOLDER_PATTERNS:
            if re.search(pattern, line):
                out.append(Finding("K3", "warn", str(path), no,
                                   f"{label} im Befehl",
                                   "Konkreten Wert einsetzen oder als Variable oben im Block definieren"))
                break
        if re.match(r"\s*(\./|bash\s+\./|python3?\s+\./)", line):
            out.append(Finding("K3", "warn", str(path), no,
                               "Relativer Aufruf — haengt vom Arbeitsverzeichnis ab",
                               "Pfad ueber eine Variable verankern (z.B. REPO=~/... ; \"$REPO/scripts/x.py\")"))
        for pattern, hint in TOKEN_WASTERS:
            if re.search(pattern, line) and not any(f in line for f in FILTER_HINTS):
                out.append(Finding("K8", "warn", str(path), no, hint,
                                   "Ausgabe eingrenzen oder das dedizierte Tool nutzen"))
                break
        if re.search(r"\bmkdir\s+(?!-p)", line):
            out.append(Finding("K9", "warn", str(path), no,
                               "mkdir ohne -p — zweiter Lauf schlaegt fehl",
                               "mkdir -p verwenden"))
        if re.search(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r", line):
            out.append(Finding("K9", "block", str(path), no,
                               "rm -rf im Ablauf",
                               "Loeschung entfernen oder auf einen exakt benannten Pfad einschraenken"))
    return out


def check_structure(path: Path, text: str) -> list[Finding]:
    """K4 Verifikation, K5 Fehlerpfad, K6 Reihenfolge."""
    out: list[Finding] = []
    low = text.lower()
    if not any(m in low for m in VERIFY_MARKERS):
        out.append(Finding("K4", "warn", str(path), 1,
                           "Kein Verifikationsschritt",
                           "Pro Schritt die erwartete Ausgabe nennen oder einen Pruefbefehl ergaenzen"))
    if not any(m in low for m in ERROR_MARKERS):
        out.append(Finding("K5", "warn", str(path), 1,
                           "Kein Fehlerpfad",
                           "Abschnitt 'Wenn etwas fehlschlaegt' mit Symptom -> Massnahme ergaenzen"))
    if not re.search(r"^\s*1\.\s", text, re.MULTILINE):
        out.append(Finding("K6", "info", str(path), 1,
                           "Keine nummerierten Schritte",
                           "Ablauf als nummerierte Liste — schwache Modelle springen sonst"))
    return out


def check_requirements(path: Path, text: str, is_skill: bool) -> list[Finding]:
    """K7 — externe Voraussetzungen ohne requires.json."""
    out: list[Finding] = []
    if not is_skill:
        return out
    if (path.parent / "requires.json").exists():
        return out
    used: set[str] = set()
    for _, line, in_code, lang in iter_lines(text):
        if not in_code or lang not in SHELL_LANGS:
            continue
        if re.match(r"\s*(export\s+|local\s+)?[a-zA-Z_][a-zA-Z0-9_]*=", line):
            continue  # Variablenzuweisung, kein Kommando
        match = re.match(r"\s*([a-zA-Z][a-zA-Z0-9_.-]*)\b", line)
        if match and match.group(1) not in COMMON_CMDS:
            used.add(match.group(1))
    for cmd in sorted(used):
        out.append(Finding("K7", "warn", str(path), 1,
                           f"'{cmd}' wird aufgerufen, aber keine requires.json vorhanden",
                           f'requires.json anlegen: {{"requires": [{{"type": "cmd", '
                           f'"value": "{cmd}", "hint": "..."}}]}}'))
    return out


def check_size(path: Path, text: str) -> list[Finding]:
    """K8 — Umfang. Grobe Schaetzung: 4 Zeichen ~ 1 Token."""
    tokens = len(text) // 4
    if tokens > 3000:
        return [Finding("K8", "warn", str(path), 1,
                        f"~{tokens} Tokens — laedt bei jedem Aufruf mit",
                        "Details in referenzierte Dateien auslagern, SKILL.md unter ~3000 Tokens halten")]
    return []


def audit_file(path: Path) -> list[Finding]:
    """Prueft eine Markdown-Datei. `SKILL.md` zieht zusaetzlich die Skill-Checks."""
    text = path.read_text(encoding="utf-8")
    is_skill = path.name == "SKILL.md"
    findings: list[Finding] = []
    findings += check_frontmatter(path, text, is_skill)
    findings += check_prose(path, text)
    findings += check_code_blocks(path, text)
    findings += check_structure(path, text)
    findings += check_requirements(path, text, is_skill)
    findings += check_size(path, text)
    return findings


def collect_targets(raw: str) -> list[Path]:
    """Loest ein Argument zu Markdown-Dateien auf (Datei, Skill-Ordner oder Baum)."""
    path = Path(raw).expanduser()
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Pfad existiert nicht: {path}")
    skill = path / "SKILL.md"
    if skill.is_file():
        return [skill]
    return sorted(path.rglob("SKILL.md"))


def score(findings: list[Finding]) -> int:
    """KISS-Score 0-100. Rein additiv, damit zwei Laeufe denselben Wert liefern."""
    penalty = sum(SEVERITY_WEIGHT[f.severity] for f in findings)
    return max(0, 100 - penalty)


def render(findings: list[Finding], targets: list[Path]) -> str:
    """Deterministischer Markdown-Report."""
    lines = ["# KISSD-Report", ""]
    lines.append(f"Geprueft: {len(targets)} Datei(en) — "
                 f"KISS-Score **{score(findings)}/100**")
    lines.append("")
    counts = {sev: sum(1 for f in findings if f.severity == sev)
              for sev in ("block", "warn", "info")}
    lines.append(f"block: {counts['block']} | warn: {counts['warn']} | info: {counts['info']}")
    lines.append("")
    if not findings:
        lines.append("Keine Befunde.")
        return "\n".join(lines) + "\n"
    lines.append("| Check | Sev | Datei:Zeile | Befund | Vorschlag |")
    lines.append("|---|---|---|---|---|")
    for f in findings:
        lines.append(f"| {f.check} | {f.severity} | {f.file}:{f.line} | "
                     f"{f.message} | {f.fix} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KISSD-Lint fuer Skills und Workflows")
    parser.add_argument("targets", nargs="+", help="SKILL.md, Skill-Ordner oder Verzeichnisbaum")
    parser.add_argument("--json", action="store_true", help="Maschinenlesbare Ausgabe")
    parser.add_argument("--strict", action="store_true", help="Exit 1 auch bei warn")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for raw in args.targets:
        try:
            files.extend(collect_targets(raw))
        except FileNotFoundError as exc:
            print(f"FEHLER: {exc}", file=sys.stderr)
            return 2
    if not files:
        print("FEHLER: keine SKILL.md oder Markdown-Datei gefunden", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for path in files:
        findings.extend(audit_file(path))
    findings.sort(key=lambda f: (f.file, f.check, f.line, f.message))

    if args.json:
        print(json.dumps({"score": score(findings),
                          "files": [str(p) for p in files],
                          "findings": [asdict(f) for f in findings]},
                         indent=2, ensure_ascii=False))
    else:
        print(render(findings, files), end="")

    if any(f.severity == "block" for f in findings):
        return 1
    if args.strict and any(f.severity == "warn" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
