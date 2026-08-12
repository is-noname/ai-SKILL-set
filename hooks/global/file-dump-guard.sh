#!/bin/bash
# PreToolUse Bash: Blockt Voll-Dumps grosser Dateien (cat/head/tail/sed/less/more).
#
# Hintergrund: eine Shell-Ausgabe kippt die komplette Datei als Kontextlast ins Fenster
# und umgeht den read-size-guard, der nur auf das Read-Tool matched. Gemessen im
# Token-Review 12.08.2026: 411 Aufrufe, 187.015 Tokens = 72 % der Bash-Kontextlast.
#
# Laesst durch: Pipelines (| grep, | wc, | jq), Umleitungen (>, >>), Heredocs,
# begrenzte Ausschnitte (head -30, sed -n '10,60p') und Dateien unter dem Schwellwert.
# Schwellwert ueber FILE_DUMP_GUARD_MAX_LINES setzbar (Default 120).
#
# Warum 120 und nicht 300: 120 Zeilen sind ein Ausschnitt zum Nachsehen, 300 sind ein
# halbes Modul. Ein sed -n '1,300p' kippt rund 3.000 Tokens ohne Zeilennummern ins
# Fenster, die ein Edit adressieren koennte - danach folgt oft ein zweiter, echter
# Read derselben Datei (Doppelkosten). Fuer Dateiinhalt ist Read mit offset/limit
# das richtige Werkzeug. Gemessen im Token-Review 12.08.2026 (IZG-T-126).
#
# Braucht: python3 (Kommando-Zerlegung), jq nicht noetig.

INPUT=$(cat)

MAX_LINES="${FILE_DUMP_GUARD_MAX_LINES:-120}" python3 - "$INPUT" <<'PY'
import json, os, re, shlex, sys

MAX = int(os.environ.get("MAX_LINES") or 120)

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


def offenders(segment):
    # Pipeline oder Umleitung: die Ausgabe wird gefiltert bzw. geht in eine Datei
    if "|" in segment or ">" in segment or "<<" in segment:
        return []
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return []  # unparsebar -> fail open
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

    found = []
    for name in candidates:
        if name.startswith("$"):
            continue
        hit = too_big(name)
        if hit:
            found.append((name, hit[0], hit[1]))
    return found


hits = []
for segment in split_commands(command):
    hits.extend(offenders(segment))

if not hits:
    sys.exit(0)

name, lines, tokens = hits[0]
reason = (
    "Voll-Dump von %s (%d Zeilen) blockiert - das kippt ~%d Tokens Kontextlast ins Fenster. "
    "Nutze Read mit offset/limit auf den relevanten Abschnitt, oder Grep mit Pattern. "
    "Wenn die Ausgabe wirklich vollstaendig gebraucht wird: in eine Pipeline filtern "
    "(| grep, | wc) oder FILE_DUMP_GUARD_MAX_LINES hochsetzen."
    % (os.path.basename(name), lines, tokens)
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
