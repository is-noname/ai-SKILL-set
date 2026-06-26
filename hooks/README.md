# hooks/

Optionale Claude-Code-Hooks für dieses Repo-Setup. Jeder Hook ist ein eigenständiges
Shell-Skript, das von Claude Code zu einem bestimmten Zeitpunkt (Event) aufgerufen wird.
Hooks lesen ihren Input als JSON von `stdin` und steuern Claude über JSON auf `stdout`
(`permissionDecision: deny|ask`, `additionalContext`, `systemMessage`) bzw. über den
Exit-Code (`exit 2` = harter Abbruch).

> **Voraussetzung:** `jq` muss installiert sein (alle Guards parsen ihren JSON-Input damit).
> `piper-notify.sh` braucht zusätzlich `python3`, Piper-TTS und `aplay`.

---

## Global vs. Projekt

Die meisten Hooks sind **global** sinnvoll (Sicherheit, Git-Schutz) und gehören nach
`~/.claude/settings.json` mit absoluten Pfaden auf `~/.claude/hooks/`. Zwei Hooks sind
**projektgebunden**:

| Hook | Scope | Grund |
|------|-------|-------|
| `pre-commit-registry.sh` | nur dieses Repo | Hardcodierter Pfad auf `ai-SKILL-set`, regeneriert `registry.json` |
| `ticket-mover.sh` | global ODER pro Projekt | Funktioniert in jedem Repo mit `tickets/`-Struktur |

Alle anderen sind reine global-Guards ohne Projektbezug.

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
| `git-commit-guard.sh` | Setzt `ask` — Commit nur nach expliziter User-Anfrage. | Bei `git commit`. |
| `git-push-guard.sh` | `git push` → `ask`; `git push --force` → **deny**. | Bei jedem `git push`. |
| `git-destructive-guard.sh` | Blockt `reset --hard`, `clean -f`, `checkout .`, `branch -D`, `rebase`. | Bei destruktiven Git-Operationen. |
| `gh-cli-guard.sh` | Blockt Repo-Visibility-Änderung, `repo create --public`, `pr/issue create`, `repo delete` / `api … DELETE`. | Bei riskanten `gh`-Befehlen. |
| `pre-commit-registry.sh` | Regeneriert `registry.json`, wenn `SKILL.md`-Dateien gestaged sind; bricht den Commit ab (`exit 2`), falls die Validierung fehlschlägt. | Bei `git commit` in diesem Repo. |

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

1. **Skripte ablegen** (global) und ausführbar machen:

   ```bash
   cp hooks/*.sh hooks/dir-scope.conf ~/.claude/hooks/
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

3. **`pre-commit-registry.sh`** ist repo-spezifisch (fester Pfad auf `ai-SKILL-set`).
   Nur registrieren, wenn du in genau diesem Repo arbeitest — als zusätzlicher
   `Bash`-Eintrag unter `PreToolUse`. Für andere Repos den Pfad im Skript anpassen.

4. **Neustart / neue Session** — Claude Code lädt `settings.json` beim Start.

### Hinweise

- **`ask` vs. `deny`:** `git-commit-guard` und `git-push` (ohne `--force`) fragen nur
  nach; alles andere blockiert hart. Anpassen über `permissionDecision` im jeweiligen Skript.
- **Reihenfolge:** Mehrere Hooks pro matcher laufen in Listenreihenfolge; der erste
  `deny` gewinnt.
- **Debugging:** Hooks mit `echo … >&2` schreiben auf stderr (z. B. `ticket-mover`,
  `pre-commit-registry`); diese Ausgabe erscheint im Hook-Log.
