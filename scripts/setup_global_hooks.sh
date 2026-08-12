#!/usr/bin/env bash
# Deployer fuer die globalen Guard-/Helfer-Hooks aus hooks/global/. Eigene Domaene,
# NICHT zu verwechseln mit setup_global_conventions.sh (Konventions-Buendel: Tickets,
# doc-ids, project-identifier). ticket-mover wird hier bewusst NICHT angeboten — er
# gehoert zum Konventions-Deployer.
#
# Interaktive Auswahl: zeigt pro Hook den Drift-Status (ok/drift/missing) und fragt,
# welche installiert/aktualisiert werden. Keine Blind-Installation aller Hooks.
# Drift wird angezeigt + abgefragt, nie blind ueberschrieben.
#
# Registrierung der Hooks in settings.json erfolgt nur fuer .claude (das Hook-Format
# ist Claude-spezifisch). Andere Agent-Dirs werden nicht unterstuetzt.
#
# Usage:
#   bash setup_global_hooks.sh                 # interaktiv, Ziel ~/.claude
#   bash setup_global_hooks.sh ~/.claude       # explizites Agent-Dir
#   bash setup_global_hooks.sh --check         # read-only Drift-Report, keine Aenderung
#   bash setup_global_hooks.sh --all           # alle Guards (nicht-interaktiv)
#   bash setup_global_hooks.sh --hooks git-push-guard,protect-env   # gezielte Auswahl
#   bash setup_global_hooks.sh --all --force   # ohne Drift-Rueckfragen ueberschreiben
#
# Exit: 0 = ok, 1 = Drift gefunden (nur --check), 2 = Aufruf-/Repo-Fehler.

set -o pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_SRC="$REPO_ROOT/hooks/global"

# Hook-Registry: name | event | matcher  (matcher leer = kein matcher, z.B. Notification)
# Reihenfolge = Registrierungs-Reihenfolge. ticket-mover fehlt absichtlich (Konvention).
HOOK_SPECS=(
  "protect-env|PreToolUse|Read|Edit|Write"
  "protect-env|PreToolUse|Bash"
  "dir-scope-guard|PreToolUse|Read|Edit|Write"
  "read-size-guard|PreToolUse|Read"
  "env-key-guard|PreToolUse|Bash"
  "file-dump-guard|PreToolUse|Bash"
  "git-commit-guard|PreToolUse|Bash"
  "git-push-guard|PreToolUse|Bash"
  "git-destructive-guard|PreToolUse|Bash"
  "gh-cli-guard|PreToolUse|Bash"
  "piper-notify|Notification|"
  "check-chatbox|SessionStart|startup"
)

# spec zerlegen: das matcher-Feld kann selbst | enthalten (Read|Edit|Write), daher
# name = vor dem 1. |, event = vor dem 2. |, matcher = Rest.
_spec_name()    { printf '%s' "${1%%|*}"; }
_spec_event()   { local r="${1#*|}"; printf '%s' "${r%%|*}"; }
_spec_matcher() { local r="${1#*|}"; printf '%s' "${r#*|}"; }

ALL_NAMES=()
for s in "${HOOK_SPECS[@]}"; do
  n="$(_spec_name "$s")"
  # dedupe - ein Hook kann mehrfach in HOOK_SPECS stehen (z.B. protect-env unter
  # zwei Mattern), soll aber nur einmal deployt/gefragt werden.
  case " ${ALL_NAMES[*]} " in *" $n "*) continue ;; esac
  ALL_NAMES+=("$n")
done

# --- Argumente ---
AGENT_DIR=""
MODE="interactive"   # interactive | check | all | named
NAMED=""
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --all)   MODE="all" ;;
    --hooks=*) MODE="named"; NAMED="${arg#--hooks=}" ;;
    --hooks)  MODE="named" ;;                 # naechstes Arg ist die Liste
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --*) echo "Unbekannte Option: $arg" >&2; exit 2 ;;
    *)
      if [ "$MODE" = "named" ] && [ -z "$NAMED" ]; then NAMED="$arg"
      else AGENT_DIR="$arg"; fi
      ;;
  esac
done
AGENT_DIR="${AGENT_DIR:-$HOME/.claude}"
AGENT_DIR="$(eval echo "$AGENT_DIR")"
agent_name="$(basename "$AGENT_DIR")"

if [ ! -d "$HOOKS_SRC" ]; then
  echo "Error: $HOOKS_SRC fehlt — Repo unvollstaendig ausgecheckt?" >&2; exit 2
fi
if [ ! -d "$AGENT_DIR" ]; then
  echo "Error: Agent-Dir $AGENT_DIR existiert nicht." >&2; exit 2
fi

# --- Drift-Status eines Hooks gegen das deployte Ziel ---
# Echo: ok | drift | missing
_status() {
  local name="$1" src="$HOOKS_SRC/$1.sh" dst="$AGENT_DIR/hooks/$1.sh"
  [ -f "$dst" ] || { echo "missing"; return; }
  if cmp -s "$src" "$dst"; then echo "ok"; else echo "drift"; fi
}

_status_label() {
  case "$1" in
    ok)      printf 'ok' ;;
    drift)   printf 'DRIFT (deployt weicht ab)' ;;
    missing) printf 'fehlt (nicht installiert)' ;;
  esac
}

# --- --check: read-only Report ---
if [ "$MODE" = "check" ]; then
  echo "== Hook-Drift gegen $AGENT_DIR/hooks/ =="
  rc=0
  for name in "${ALL_NAMES[@]}"; do
    st="$(_status "$name")"
    [ "$st" = "ok" ] || rc=1
    printf '  %-22s %s\n' "$name" "$(_status_label "$st")"
  done
  [ "$rc" = 1 ] && echo "" && echo "Aktualisieren/installieren: bash $0 [--all|--hooks <liste>]"
  exit "$rc"
fi

# --- Auswahl bestimmen ---
SELECTED=()
case "$MODE" in
  all)
    SELECTED=("${ALL_NAMES[@]}")
    ;;
  named)
    IFS=',' read -ra want <<< "$NAMED"
    for w in "${want[@]}"; do
      w="$(printf '%s' "$w" | tr -d '[:space:]')"
      [ -z "$w" ] && continue
      if [ -f "$HOOKS_SRC/$w.sh" ]; then SELECTED+=("$w")
      else echo "Warnung: unbekannter Hook '$w' — uebersprungen." >&2; fi
    done
    ;;
  interactive)
    echo "== Verfuegbare Hooks (Quelle: hooks/global/, Ziel: $AGENT_DIR/hooks/) =="
    echo "   y = installieren/aktualisieren, n/Enter = ueberspringen"
    echo ""
    for name in "${ALL_NAMES[@]}"; do
      st="$(_status "$name")"
      ans=""
      printf '  %-22s [%s] installieren? [y/N] ' "$name" "$(_status_label "$st")"
      read -r ans < /dev/tty || ans=""
      case "$ans" in [yYjJ]*) SELECTED+=("$name") ;; esac
    done
    ;;
esac

if [ "${#SELECTED[@]}" -eq 0 ]; then
  echo "Nichts ausgewaehlt — keine Aenderung."; exit 0
fi

# --- Deploy ---
mkdir -p "$AGENT_DIR/hooks"
DEPLOYED=()
for name in "${SELECTED[@]}"; do
  src="$HOOKS_SRC/$name.sh"; dst="$AGENT_DIR/hooks/$name.sh"
  st="$(_status "$name")"
  if [ "$st" = "drift" ] && [ "$FORCE" -ne 1 ]; then
    ans=""
    printf '  %s: deployt weicht ab — ueberschreiben? [y/N] ' "$name"
    read -r ans < /dev/tty || ans=""
    case "$ans" in [yYjJ]*) ;; *) echo "  $name: uebersprungen (Drift behalten)"; continue ;; esac
  fi
  cp "$src" "$dst" && chmod +x "$dst"
  echo "  deployed: $dst"
  DEPLOYED+=("$name")
  # dir-scope-guard braucht seine Konfig — aber nie eine vorhandene (user-editierte)
  # ueberschreiben. Nur anlegen wenn sie fehlt.
  if [ "$name" = "dir-scope-guard" ]; then
    conf_dst="$AGENT_DIR/hooks/dir-scope.conf"
    if [ ! -f "$conf_dst" ]; then
      cp "$HOOKS_SRC/dir-scope.conf" "$conf_dst"
      echo "  deployed: $conf_dst (Vorlage — Pfade anpassen)"
    else
      echo "  $conf_dst existiert — nicht ueberschrieben (user-editiert)"
    fi
  fi
done

[ "${#DEPLOYED[@]}" -eq 0 ] && { echo "Keine Datei deployt."; exit 0; }

# --- settings.json-Registrierung (nur Claude) ---
if [ "$agent_name" != ".claude" ]; then
  echo ""
  echo "Hinweis: $agent_name ist nicht .claude — Hook-Dateien liegen bereit, aber die"
  echo "settings.json-Registrierung ist Claude-spezifisch und wird hier nicht gepatcht."
  exit 0
fi

settings="$AGENT_DIR/settings.json"
if [ ! -f "$settings" ]; then
  echo ""; echo "$settings nicht gefunden — Hooks liegen bereit, manuell registrieren."
  exit 0
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo ""; echo "python3 fehlt — settings.json nicht gepatcht (Hooks liegen bereit)."
  exit 0
fi

# Registrierungs-Spec als JSON bauen: [{event, matcher, command}, ...]
spec_json="["
first=1
for name in "${DEPLOYED[@]}"; do
  for s in "${HOOK_SPECS[@]}"; do
    [ "$(_spec_name "$s")" = "$name" ] || continue
    ev="$(_spec_event "$s")"; mt="$(_spec_matcher "$s")"
    cmd="$AGENT_DIR/hooks/$name.sh"
    [ "$first" -eq 1 ] && first=0 || spec_json+=","
    spec_json+="{\"event\":\"$ev\",\"matcher\":\"$mt\",\"command\":\"$cmd\"}"
  done
done
spec_json+="]"

python3 - "$settings" "$spec_json" <<'PY'
import json, sys
settings_path, spec_raw = sys.argv[1], sys.argv[2]
spec = json.loads(spec_raw)
with open(settings_path) as f:
    data = json.load(f)
hooks = data.setdefault("hooks", {})
added, skipped = [], []
for item in spec:
    event, matcher, command = item["event"], item["matcher"], item["command"]
    arr = hooks.setdefault(event, [])
    # Dedupe pro (event, matcher, command) - derselbe Hook kann unter mehreren
    # Mattern registriert sein (z.B. protect-env unter Read|Edit|Write UND Bash),
    # das ist kein Duplikat. Nur identische matcher+command ist eins.
    already = any(
        entry.get("matcher", "") == matcher and h.get("command") == command
        for entry in arr
        for h in entry.get("hooks", [])
    )
    if already:
        skipped.append(command.rsplit("/", 1)[-1])
        continue
    # passenden Eintrag (gleicher matcher) suchen, sonst neu anlegen
    target = None
    for entry in arr:
        if entry.get("matcher", "") == matcher:
            target = entry
            break
    if target is None:
        target = {"hooks": []} if matcher == "" else {"matcher": matcher, "hooks": []}
        arr.append(target)
    target.setdefault("hooks", []).append({"type": "command", "command": command})
    added.append(command.rsplit("/", 1)[-1])
if added:
    with open(settings_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("  patched: settings.json — registriert:", ", ".join(added))
if skipped:
    print("  bereits registriert (uebersprungen):", ", ".join(skipped))
PY

echo ""
echo "Fertig. Neue Session starten, damit Claude Code settings.json neu laedt."
echo "Hinweis: Reihenfolge der Bash-Hooks ggf. pruefen (ask/deny brechen die Kette ab —"
echo "siehe hooks/README.md). Re-Check jederzeit: bash $0 --check"
