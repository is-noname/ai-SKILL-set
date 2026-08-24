#!/bin/bash
# PreToolUse Bash: Blockt Voll-Dumps grosser Dateien (cat/head/tail/sed/less/more).
#
# Hintergrund: eine Shell-Ausgabe kippt die komplette Datei als Kontextlast ins Fenster
# und umgeht den read-size-guard, der nur auf das Read-Tool matched. Gemessen im
# Token-Review 12.08.2026: 411 Aufrufe, 187.015 Tokens = 72 % der Bash-Kontextlast.
#
# Zweiter Pfad (IZG-T-160): Verzeichnis-Dumps (ls -l/-R, find). Die Ausgabe entsteht
# hier erst zur Laufzeit, es gibt keine Datei zum Zeilenzaehlen. Deshalb entscheidet
# ls ueber die Zahl der Eintraege im Zielverzeichnis (FILE_DUMP_GUARD_MAX_ENTRIES,
# Default 40) und find strukturell: ohne -name/-maxdepth/-exec und ohne echten
# nachgeschalteten Filter ist die Trefferzahl unbegrenzt. Gemessen im Token-Review
# 22.08.2026 (SCU-T-040): ls -la 18x/10.523 Tokens, find 10x/5.861 Tokens.
#
# Laesst durch: Pipelines (| grep, | wc, | jq), Umleitungen (>, >>), Heredocs,
# begrenzte Ausschnitte (head -30, sed -n '10,60p'), Dateien unter dem Schwellwert,
# kurze Verzeichnisse und gefilterte find-Aufrufe.
# Schwellwerte ueber FILE_DUMP_GUARD_MAX_LINES (Default 120) und
# FILE_DUMP_GUARD_MAX_ENTRIES (Default 40) setzbar.
#
# Warum 120 und nicht 300: 120 Zeilen sind ein Ausschnitt zum Nachsehen, 300 sind ein
# halbes Modul. Ein sed -n '1,300p' kippt rund 3.000 Tokens ohne Zeilennummern ins
# Fenster, die ein Edit adressieren koennte - danach folgt oft ein zweiter, echter
# Read derselben Datei (Doppelkosten). Fuer Dateiinhalt ist Read mit offset/limit
# das richtige Werkzeug. Gemessen im Token-Review 12.08.2026 (IZG-T-126).
#
# Braucht: python3 (Kommando-Zerlegung), jq nicht noetig.

INPUT=$(cat)

MAX_LINES="${FILE_DUMP_GUARD_MAX_LINES:-120}" \
MAX_ENTRIES="${FILE_DUMP_GUARD_MAX_ENTRIES:-40}" \
python3 - "$INPUT" <<'PY'
import json, os, re, shlex, sys

MAX = int(os.environ.get("MAX_LINES") or 120)
MAX_ENTRIES = int(os.environ.get("MAX_ENTRIES") or 40)

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)  # fail open

command = (data.get("tool_input") or {}).get("command") or ""
cwd = data.get("cwd") or os.getcwd()
if not command.strip():
    sys.exit(0)

DUMPERS = {"cat", "bat", "less", "more", "tac", "nl"}


def split_commands(text):
    """Zerlegt in einzelne Kommandos an ; && || und Zeilenumbruch.
    Pipelines bleiben zusammen - sie werden als Ganzes durchgelassen."""
    return [p for p in re.split(r"(?:&&|\|\||;|\n)", text) if p.strip()]


def numeric_limit(tokens, i):
    """Liest die Zeilenzahl eines head/tail-Aufrufs. None = kein Limit gefunden."""
    tok = tokens[i]
    m = re.fullmatch(r"-(\d+)", tok)
    if m:
        return int(m.group(1))
    if tok in ("-n", "--lines") and i + 1 < len(tokens):
        m = re.fullmatch(r"[+-]?(\d+)", tokens[i + 1])
        if m:
            return int(m.group(1))
    m = re.fullmatch(r"-n[+-]?(\d+)", tok)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"--lines=[+-]?(\d+)", tok)
    if m:
        return int(m.group(1))
    return None


def sed_span(tokens):
    """Zeilenspanne eines sed -n 'A,Bp'. None = kein begrenzender Ausdruck."""
    for t in tokens:
        m = re.fullmatch(r"(\d+),(\d+)p", t.strip("'\""))
        if m:
            return int(m.group(2)) - int(m.group(1)) + 1
    return None


def file_args(tokens):
    return [t for t in tokens[1:] if not t.startswith("-")]


def too_big(name):
    """(Zeilen, geschaetzte Tokens), wenn die Datei den Schwellwert reisst - sonst None."""
    path = name if os.path.isabs(name) else os.path.join(cwd, name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            lines = sum(1 for _ in fh)
        size = os.path.getsize(path)
    except OSError:
        return None
    return (lines, size // 4) if lines > MAX else None


# --- Verzeichnis-Dumps (ls, find) -------------------------------------------
# Anders als bei cat/sed gibt es keine Datei, deren Zeilen sich zaehlen liessen:
# die Ausgabe entsteht erst beim Ausfuehren. ls laesst sich ueber die Zahl der
# Eintraege im Zielverzeichnis abschaetzen, find nur strukturell.

# Nur die breiten ls-Formen kosten wirklich: -l (eine Zeile je Eintrag) und -R
# (der ganze Baum). Ein spaltiges `ls dir` bleibt unbehelligt.
LS_WIDE_RE = re.compile(r"^-[A-Za-z]*[lR][A-Za-z]*$")

# find-Ausdruecke, die die Treffermenge begrenzen oder die Ausgabe ersetzen.
FIND_LIMITERS = {
    "-name", "-iname", "-path", "-ipath", "-regex", "-iregex",
    "-maxdepth", "-samefile", "-newer", "-quit",
    "-exec", "-execdir", "-ok", "-okdir", "-delete",
}


def ls_flags(tokens):
    """(breit, rekursiv) fuer einen ls-Aufruf."""
    wide = recursive = False
    for t in tokens[1:]:
        if t == "--":
            break
        if t.startswith("--"):
            if t == "--recursive":
                wide = recursive = True
            elif t.startswith("--format=long"):
                wide = True
            continue
        if LS_WIDE_RE.fullmatch(t):
            wide = True
            if "R" in t:
                recursive = True
    return wide, recursive


def dir_args(tokens):
    """Verzeichnis-Argumente; ohne Angabe das Arbeitsverzeichnis."""
    args = [t for t in tokens[1:] if not t.startswith("-")]
    return args or ["."]


def count_entries(name, recursive, cap):
    """Eintraege im Verzeichnis, Abbruch bei cap. None = kein zaehlbares Verzeichnis.

    Globs (ls -la *.py) und nicht existente Pfade liefern None und werden
    durchgelassen - der Guard raet nicht.
    """
    path = name if os.path.isabs(name) else os.path.join(cwd, name)
    if not os.path.isdir(path):
        return None
    n = 0
    try:
        if recursive:
            for _root, dirs, files in os.walk(path):
                n += len(dirs) + len(files)
                if n > cap:
                    return n
        else:
            with os.scandir(path) as it:
                for _ in it:
                    n += 1
                    if n > cap:
                        return n
    except OSError:
        return None
    return n


def find_unbounded(tokens):
    """True, wenn der find-Aufruf die Treffermenge durch nichts begrenzt."""
    return not any(t in FIND_LIMITERS for t in tokens[1:])


TOOTHLESS_CMDS = {"cat", "bat", "tac", "tee", "nl"}


def is_toothless(tokens):
    """True, wenn dieses Pipeline-Glied nichts herausfiltert (Schein-Filter)."""
    if not tokens:
        return True
    cmd = os.path.basename(tokens[0])
    if cmd in TOOTHLESS_CMDS:
        return True
    if cmd == "grep":
        args = tokens[1:]
        flags = []
        pattern = None
        for a in args:
            if a.startswith("-") and pattern is None:
                flags.append(a)
                continue
            pattern = a
            break
        if pattern == "":
            return True
        if pattern == "$^" and "-v" in flags:
            return True
        return False
    if cmd in ("head", "tail"):
        limit = None
        for i in range(1, len(tokens)):
            limit = numeric_limit(tokens, i)
            if limit is not None:
                break
        if limit is None:
            return False  # Default-Limit (10 Zeilen) - filtert real
        return limit > MAX
    return False  # unbekanntes Kommando: im Zweifel echter Filter


def offenders(segment):
    # Umleitung: die Ausgabe geht in eine Datei, nicht ins Kontextfenster
    if ">" in segment or "<<" in segment:
        return []
    try:
        all_tokens = shlex.split(segment)
    except ValueError:
        return []  # unparsebar -> fail open
    if not all_tokens:
        return []

    stages, current = [], []
    for t in all_tokens:
        if t == "|":
            stages.append(current)
            current = []
        else:
            current.append(t)
    stages.append(current)

    pipeline = len(stages) > 1
    if pipeline:
        # Pipeline laesst nur durch, wenn ALLE nachfolgenden Glieder Schein-Filter sind.
        # Ist mindestens ein Glied ein echter Filter, gilt die Pipeline als gefiltert.
        if not all(is_toothless(s) for s in stages[1:]):
            return []

    tokens = stages[0]
    if not tokens:
        return []

    # fuehrende Zuweisungen (FOO=bar cat x) ueberspringen
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return []

    cmd = os.path.basename(tokens[0])
    candidates = []

    if cmd in DUMPERS:
        candidates = file_args(tokens)
    elif cmd in ("head", "tail"):
        limit = None
        for i in range(1, len(tokens)):
            limit = numeric_limit(tokens, i)
            if limit is not None:
                break
        if limit is None:
            return []          # Default 10 Zeilen - unbedenklich
        if limit <= MAX:
            return []
        candidates = file_args(tokens)
    elif cmd == "sed":
        span = sed_span(tokens)
        if span is not None and span <= MAX:
            return []
        candidates = [t for t in file_args(tokens) if os.path.sep in t or os.path.isfile(
            t if os.path.isabs(t) else os.path.join(cwd, t))]
    elif cmd == "ls":
        wide, recursive = ls_flags(tokens)
        if not wide:
            return []          # spaltiges ls ist kompakt
        found = []
        for name in dir_args(tokens):
            if name.startswith("$"):
                continue
            n = count_entries(name, recursive, MAX_ENTRIES)
            if n is not None and n > MAX_ENTRIES:
                found.append({"kind": "ls", "name": name, "entries": n,
                              "recursive": recursive, "pipeline": pipeline})
        return found
    elif cmd == "find":
        if not find_unbounded(tokens):
            return []          # -name/-maxdepth/-exec begrenzen bereits
        return [{"kind": "find", "name": (dir_args(tokens) or ["."])[0],
                 "pipeline": pipeline}]

    found = []
    for name in candidates:
        if name.startswith("$"):
            continue
        hit = too_big(name)
        if hit:
            found.append({"kind": "file", "name": name, "lines": hit[0],
                          "tokens": hit[1], "pipeline": pipeline})
    return found


hits = []
for segment in split_commands(command):
    hits.extend(offenders(segment))

if not hits:
    sys.exit(0)

hit = hits[0]
kind = hit["kind"]
pipeline = hit["pipeline"]

if kind == "ls":
    form = "ls -R" if hit["recursive"] else "ls -la"
    reason = (
        "Verzeichnis-Dump von %s (%s%d Eintraege) blockiert - ein langes Listing kostet "
        "rund 10 Tokens je Zeile Kontextlast. Nutze das Glob-Tool fuer Dateinamen, oder "
        "filtere: '%s %s | head -20', '%s %s | grep <pattern>'. "
        "Schwellwert notfalls ueber FILE_DUMP_GUARD_MAX_ENTRIES hochsetzen."
        % (hit["name"], "mindestens " if hit["recursive"] else "", hit["entries"],
           form, hit["name"], form, hit["name"])
    )
elif kind == "find":
    reason = (
        "Ungefiltertes find unter %s blockiert - die Trefferzahl ist durch nichts begrenzt "
        "und landet vollstaendig im Kontextfenster. Grenze ein (-name, -maxdepth), nutze "
        "das Glob-Tool, oder filtere nach: '| head -20', '| grep <pattern>', '| wc -l'."
        % hit["name"]
    )
else:
    reason = (
        "Voll-Dump von %s (%d Zeilen) blockiert - das kippt ~%d Tokens Kontextlast ins Fenster. "
        "Nutze Read mit offset/limit auf den relevanten Abschnitt, oder Grep mit Pattern. "
        "Wenn die Ausgabe wirklich vollstaendig gebraucht wird: in eine Pipeline filtern "
        "(| grep, | wc) oder FILE_DUMP_GUARD_MAX_LINES hochsetzen."
        % (os.path.basename(hit["name"]), hit["lines"], hit["tokens"])
    )

if pipeline and kind == "file":
    reason += (
        " Diese Pipeline filtert nicht wirklich - 'grep -n \"\"' o.ae. matcht jede "
        "Zeile und nummeriert nur. Read mit offset/limit liefert Zeilennummern gratis mit."
    )
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
}))
PY
exit 0
