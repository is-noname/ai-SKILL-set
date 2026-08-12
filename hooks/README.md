# hooks/

Optionale Claude-Code-Hooks für dieses Repo-Setup. Jeder Hook ist ein eigenständiges
Shell-Skript, das von Claude Code zu einem bestimmten Zeitpunkt (Event) aufgerufen wird.
Hooks lesen ihren Input als JSON von `stdin` und steuern Claude über JSON auf `stdout`
(`permissionDecision: deny|ask`, `additionalContext`, `systemMessage`) bzw. über den
Exit-Code (`exit 2` = harter Abbruch).

> **Voraussetzung:** `jq` muss installiert sein (alle Guards parsen ihren JSON-Input damit).
> `file-dump-guard.sh` nutzt stattdessen `python3` für die Kommando-Zerlegung.
> `piper-notify.sh` braucht zusätzlich `python3`, Piper-TTS und `aplay`.

---

## Ordnerstruktur — global/ vs. repo-local/

Die Hooks liegen im Repo in zwei Unterordnern nach **Default-Deploy-Ort**:

| Ordner | Hooks | Bedeutung |
|--------|-------|-----------|
| `hooks/global/` | alle Guards (`protect-env`, `dir-scope-guard` +`dir-scope.conf`, `env-key-guard`, `file-dump-guard`, `gh-cli-guard`, `git-*-guard`, `read-size-guard`) sowie `piper-notify`, `check-chatbox`, `ticket-mover` | einmal in `~/.claude/hooks/` aufgesetzt, feuert überall, wird nie neu aufgesetzt |
| `hooks/repo-local/` | `pre-commit-registry`, `pre-commit-agentdocs`, `pre-commit-toc` | wirken nur im `ai-SKILL-set`-Repo, nie global deployt |

**Wichtig:** Die Unterordner gibt es nur im **Repo**. Beim Deploy landen die Skripte
flach in `~/.claude/hooks/` — die `settings.json`-Pfade unten zeigen deshalb auf
`~/.claude/hooks/<skript>.sh` (ohne `global/`).

Sonderfall `ticket-mover.sh`: Default ist global, funktioniert aber in jedem Repo mit
`tickets/`-Struktur, weil er den Pfad aus dem Hook-Input ableitet (kein hardcodierter
Pfad). Eine **einzige globale Registrierung deckt alle Projekte ab** — eine zusätzliche
Pro-Projekt-Registrierung wäre kein Zusatz, sondern würde nur doppelt feuern. Pro-Projekt
nur sinnvoll als **Ersatz**, falls man ihn bewusst nicht global will.

---

## Hook-Übersicht

### PreToolUse — Read / Edit / Write

| Hook | Was er tut | Wann er feuert |
|------|------------|----------------|
| `protect-env.sh` | Blockt jeden Zugriff auf Pfade die `.env` enthalten (API-Key-Schutz). | Vor Read/Edit/Write auf eine `.env*`-Datei. |
| `dir-scope-guard.sh` | Blockt Zugriff auf sensible Verzeichnisse aus `dir-scope.conf` (Privat, Steuern, `.ssh`, `.gnupg`, …). | Vor Read/Edit/Write, wenn der Zielpfad unter einem `BLOCKED_DIRS`-Eintrag liegt. |
| `read-size-guard.sh` | Blockt `.jsonl`/`.log` hart; warnt (kein Block) bei Dateien > 1000 Zeilen und empfiehlt `offset`/`limit`. | Vor jedem Read. |

`dir-scope-guard.sh` liest seine Konfig aus `~/.claude/hooks/dir-scope.conf` (mitliefern).

### PreToolUse — Bash

| Hook | Was er tut | Wann er feuert |
|------|------------|----------------|
| `env-key-guard.sh` | Blockt `env`/`printenv` (nackt oder per `grep`-Pipe) und direkte Expansion bekannter Key-Variablen (`$ANTHROPIC*`, `$OPENAI*`, `$*TOKEN` …). | Vor Bash-Befehlen, die Keys aus dem Environment auslesen könnten. |
| `file-dump-guard.sh` | Blockt Voll-Dumps von Dateien > 300 Zeilen (`cat`, `less`, `nl`, `head -n 2000`, `sed` ohne begrenzenden Ausdruck) und verweist auf Read mit `offset`/`limit`. Pipelines, Umleitungen, Heredocs und begrenzte Ausschnitte laufen durch. Schwellwert über `FILE_DUMP_GUARD_MAX_LINES`. | Vor Bash-Befehlen, die eine Datei vollständig ausgeben. Braucht `python3`. |
| `git-commit-guard.sh` | Setzt `ask` — Commit nur nach expliziter User-Anfrage. | Bei `git commit`. |
| `git-push-guard.sh` | `git push` → `ask`; `git push --force` → **deny**. | Bei jedem `git push`. |
| `git-destructive-guard.sh` | Blockt `reset --hard`, `clean -f`, `checkout .`, `branch -D`, `rebase`. | Bei destruktiven Git-Operationen. |
| `gh-cli-guard.sh` | Blockt Repo-Visibility-Änderung, `repo create --public`, `pr/issue create`, `repo delete` / `api … DELETE`. | Bei riskanten `gh`-Befehlen. |
| `pre-commit-registry.sh` | Regeneriert `registry.json`, wenn `SKILL.md`-Dateien gestaged sind; bricht den Commit ab (`exit 2`), falls die Validierung fehlschlägt. | Bei `git commit` in diesem Repo. |
| `pre-commit-agentdocs.sh` | Regeneriert `CLAUDE.md`/`GEMINI.md` aus `AGENTS.md` (Source of Truth) und stagt sie nach, wenn eine der drei Root-Configs gestaged ist; bricht ab (`exit 2`) bei Fehler. | Bei `git commit` in diesem Repo. |
| `pre-commit-toc.sh` | Aktualisiert das Kopf-Inhaltsverzeichnis (Funktionsname + Zeilennummer, via `scripts/update_script_toc.py`) von `scripts/setup_global_conventions.sh` und `scripts/tickets.sh` und stagt sie nach, wenn eine der beiden gestaged ist; bricht ab (`exit 2`) bei Fehler. | Bei `git commit` in diesem Repo. |

### PostToolUse — Edit / Write

| Hook | Was er tut | Wann er feuert |
|------|------------|----------------|
| `ticket-mover.sh` | Verschiebt eine Ticket-Datei in den Ordner, der ihrem `status:`-Frontmatter entspricht (`open`/`in-progress`/`blocked`/`done`). Kollisionsschutz: überschreibt kein vorhandenes Ziel. | Nach Edit/Write auf eine Datei unter `*/tickets/*` mit gültigem `id: PRJ-T-NNN`. |

### SessionStart

| Hook | Was er tut | Wann er feuert |
|------|------------|----------------|
| `check-chatbox.sh` | Meldet beim Start Inbox, offene Threads (ohne `[DONE:claude]`) und Board-Einträge der Agent-Chatbox. | Bei `SessionStart` (matcher `startup`), nur wenn `agent_chatbox/` im cwd existiert. |

### Notification

| Hook | Was er tut | Wann er feuert |
|------|------------|----------------|
| `piper-notify.sh` | Spricht „Agent wartet auf Eingabe" per Piper-TTS — nur bei `permission_prompt`, nicht bei idle/auth. | Bei Notification-Events. Braucht `~/.config/piper/defaults`. |

### Konfigurationsdatei (kein Hook)

| Datei | Zweck |
|-------|-------|
| `dir-scope.conf` | `BLOCKED_DIRS`-Array für `dir-scope-guard.sh`. Wird mit `source` geladen, Pfade absolut oder mit `~`/`$HOME`. |

---

## Installation

### Automatisch (empfohlen): `setup_global_hooks.sh`

Statt manuell zu kopieren und `settings.json` zu editieren, deployt
`scripts/setup_global_hooks.sh` die Guard-/Helfer-Hooks aus `hooks/global/` **interaktiv**
nach `~/.claude/hooks/` und registriert die gewählten in `settings.json` (Event/Matcher
pro Hook bereits hinterlegt). `ticket-mover` ist hier bewusst **nicht** dabei — der
gehört zum Konventions-Deployer `setup_global_conventions.sh`.

```bash
bash scripts/setup_global_hooks.sh            # interaktive Auswahl, Ziel ~/.claude
bash scripts/setup_global_hooks.sh --check    # read-only: zeigt ok/drift/missing pro Hook
bash scripts/setup_global_hooks.sh --all      # alle Guards (nicht-interaktiv)
bash scripts/setup_global_hooks.sh --hooks git-push-guard,protect-env   # gezielt
```

Eigenschaften: idempotent, fragt bei Drift vor dem Überschreiben (`--force` umgeht das),
überschreibt eine vorhandene `dir-scope.conf` nie (user-editiert). Registrierung nur für
`.claude` (Hook-Format ist Claude-spezifisch).

### Manuell

1. **Skripte ablegen** (global) und ausführbar machen:

   ```bash
   cp hooks/global/*.sh hooks/global/dir-scope.conf ~/.claude/hooks/
   chmod +x ~/.claude/hooks/*.sh
   ```

2. **In `~/.claude/settings.json` registrieren.** Pfade müssen absolut sein. Beispiel
   (Auszug — passe die Auswahl an, was du brauchst):

   ```json
   {
     "hooks": {
       "PreToolUse": [
         { "matcher": "Read|Edit|Write", "hooks": [
           { "type": "command", "command": "/home/USER/.claude/hooks/protect-env.sh" },
           { "type": "command", "command": "/home/USER/.claude/hooks/dir-scope-guard.sh" }
         ]},
         { "matcher": "Read", "hooks": [
           { "type": "command", "command": "/home/USER/.claude/hooks/read-size-guard.sh" }
         ]},
         { "matcher": "Bash", "hooks": [
           { "type": "command", "command": "/home/USER/.claude/hooks/env-key-guard.sh" },
           { "type": "command", "command": "/home/USER/.claude/hooks/file-dump-guard.sh" },
           { "type": "command", "command": "/home/USER/.claude/hooks/git-commit-guard.sh" },
           { "type": "command", "command": "/home/USER/.claude/hooks/git-push-guard.sh" },
           { "type": "command", "command": "/home/USER/.claude/hooks/git-destructive-guard.sh" },
           { "type": "command", "command": "/home/USER/.claude/hooks/gh-cli-guard.sh" }
         ]}
       ],
       "PostToolUse": [
         { "matcher": "Edit|Write", "hooks": [
           { "type": "command", "command": "/home/USER/.claude/hooks/ticket-mover.sh" }
         ]}
       ],
       "SessionStart": [
         { "matcher": "startup", "hooks": [
           { "type": "command", "command": "/home/USER/.claude/hooks/check-chatbox.sh" }
         ]}
       ],
       "Notification": [
         { "hooks": [
           { "type": "command", "command": "/home/USER/.claude/hooks/piper-notify.sh" }
         ]}
       ]
     }
   }
   ```

3. **`pre-commit-registry.sh`** ist repo-spezifisch. Das Skript ermittelt das Repo
   selbst aus dem aktuellen Verzeichnis (`git rev-parse --show-toplevel`) und tut
   nur etwas, wenn dort `scripts/generate_registry.py` liegt — in fremden Repos
   läuft es wirkungslos durch. Als Projekt-Hook in `.claude/settings.json` des
   Repos eintragen (mit absolutem Pfad auf dein Klon-Verzeichnis). Weicht dein
   Layout ab, lässt sich das Repo per `AI_SKILL_SET_REPO` fest vorgeben.
   Dasselbe gilt für `pre-commit-agentdocs.sh` (Marker: `scripts/sync_agent_docs.sh`) und
   `pre-commit-toc.sh` (Marker: `scripts/update_script_toc.py`).

   **Wichtig — Reihenfolge:** `pre-commit-registry.sh` muss **vor** `git-commit-guard.sh`
   eingetragen werden. `ask` bricht die Hook-Chain ab (der User entscheidet, danach
   läuft das Tool direkt — keine weiteren Hooks). Steht der Registry-Hook danach, wird
   er nie ausgeführt und `registry.json` ist veraltet ohne Fehler.

   ```json
   { "matcher": "Bash", "hooks": [
     { "type": "command", "command": "/home/USER/.claude/hooks/env-key-guard.sh" },
     { "type": "command", "command": "/path/to/ai-SKILL-set/hooks/repo-local/pre-commit-registry.sh" },
     { "type": "command", "command": "/home/USER/.claude/hooks/git-commit-guard.sh" },
     { "type": "command", "command": "/home/USER/.claude/hooks/git-push-guard.sh" },
     { "type": "command", "command": "/home/USER/.claude/hooks/git-destructive-guard.sh" },
     { "type": "command", "command": "/home/USER/.claude/hooks/gh-cli-guard.sh" }
   ]}
   ```

4. **Neustart / neue Session** — Claude Code lädt `settings.json` beim Start.

### Hinweise

- **`ask` vs. `deny`:** `git-commit-guard` und `git-push` (ohne `--force`) fragen nur
  nach; alles andere blockiert hart. Anpassen über `permissionDecision` im jeweiligen Skript.
- **Reihenfolge:** Mehrere Hooks pro matcher laufen in Listenreihenfolge. `deny` und `ask`
  brechen die Chain ab — nachfolgende Hooks laufen nicht mehr. Hooks die Side-Effects
  brauchen (z. B. `pre-commit-registry.sh`) müssen deshalb **vor** guard-Hooks stehen.
- **Debugging:** Hooks mit `echo … >&2` schreiben auf stderr (z. B. `ticket-mover`,
  `pre-commit-registry`); diese Ausgabe erscheint im Hook-Log.
