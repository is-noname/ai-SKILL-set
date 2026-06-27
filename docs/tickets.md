# Ticketsystem Konvention

> Diese Datei ist die **globale Konventions-Quelle**. Sie liegt im Verzeichnis deines
> AI-Agenten (`~/.claude`, `~/.codex`, `~/.gemini`, `~/.vibe`), wird per
> `scripts/setup_global.sh` dorthin deployt und in der Agent-Konfig
> (`CLAUDE.md` / `AGENTS.md` / …) eingebunden:
> ```markdown
> @tickets.md
> ```
> Einzelne Projekte tragen **keine** eigene Kopie — ihre `tickets/PROTOCOL.md`
> verweist auf diese Datei. Global = Konvention, pro Projekt = die Tickets selbst.

Leichtgewichtiges, file-basiertes Tracking für Bugs, Tasks, Features und Fragen.

> Diese Datei beschreibt die **Konvention** (Felder, Regeln). Wie das System intern
> funktioniert (ID-Vergabe, Status-Hook, Bootstrap-Ebenen), erklärt der
> Architektur-Guide `docs/ticketsystem-architektur.md` im ai-SKILL-set-Repo.

## Ablage

`tickets/` liegt immer im **Repo-Root**.

Falls `tickets/` noch nicht existiert, einmal pro Projekt bootstrappen
(das Script liegt im globalen Agent-Verzeichnis):
```bash
bash ~/.claude/scripts/init_tickets.sh /pfad/zum/projekt
```

```
tickets/
├── PROTOCOL.md     # Projektspezifische Regeln (optional)
├── .counter        # Zähler für Ticket-IDs (nicht manuell editieren)
├── open/
├── in-progress/
├── blocked/
└── done/
```

## Dateiname

```
{PRJ}-T-{NNN}_{kurz-beschreibung}.md
```

`{PRJ}` = Projekt-Kürzel aus der Registry `project-identifier.md` im globalen Agent-Verzeichnis.  
Nächste ID immer via Script abfragen — nie manuell zählen:

```bash
bash scripts/next_ticket_id.sh IZG
# → IZG-T-007
```

Beispiele:
```
IZG-T-001_fix-auth-bug.md
IZG-T-003_add-csv-export.md
```

## Frontmatter

```markdown
---
id: IZG-T-001
title: Auth schlägt fehl bei leerem Token
type: bug
status: open
priority: high
created: 2026-06-25
created-by: claude
assigned: gemini
started: 2026-06-25
group: auth-refactor
source: AUD-20260625-001_Auth-Review.md
---
```

| Feld | Pflicht | Werte |
|------|---------|-------|
| `id` | ja | `{PRJ}-T-{NNN}` |
| `title` | ja | Kurze Beschreibung |
| `type` | ja | `bug` / `task` / `feature` / `question` |
| `status` | ja | `open` / `in-progress` / `blocked` / `done` — Hook verschiebt die Datei automatisch |
| `priority` | ja | `high` / `normal` / `low` |
| `created` | ja | `YYYY-MM-DD` |
| `created-by` | ja | `claude` / `gemini` / `codex` / `me` |
| `assigned` | nein | `claude` / `gemini` / `codex` / `me` |
| `started` | nein | `YYYY-MM-DD` — Datum des Wechsels nach `in-progress/` |
| `group` | nein | Slug der zusammengehörige Tickets bündelt |
| `source` | nein | Dokument das das Ticket ausgelöst hat |

## Ticket-Body

```markdown
## Beschreibung

Was passiert, was sollte passieren.

## Akzeptanzkriterien

- [ ] ...

## Verlauf

### 2026-06-25 – claude
Ticket erstellt.
```

## Status-Lifecycle

```
open → in-progress → done
  ↓         ↓
blocked   blocked
  ↓         ↓
open    in-progress
```

**Regeln:**
- `status:`-Feld ändern = Status setzen — Hook verschiebt die Datei automatisch
- **Niemals manuell `mv` auf eine Ticket-Datei.** Status-Wechsel = ausschließlich das `status:`-Feld im Frontmatter editieren. Der `ticket-mover`-Hook verschiebt die Datei danach selbst in den passenden Ordner. Ein eigener `mv` schlägt fehl, weil die Datei bereits verschoben wurde.
- Jeder Statuswechsel erfordert einen Verlaufseintrag
- `blocked/` → immer zurück nach `open/`, nie direkt nach `in-progress/`
- `done/` ist finales Archiv, nicht löschen

## Lookup-Reihenfolge

1. `tickets/in-progress/` — läuft noch was?
2. `tickets/open/` — nächste sinnvolle Arbeit
3. `tickets/blocked/` — nur wenn gezielt ein Blocker gelöst werden soll

## Gruppenabfrage

```bash
grep -rl "^group: auth-refactor" tickets/
```

## question-Tickets

Werden direkt `done/` sobald die Antwort im Verlauf steht. Ergibt die Antwort eine Folgeaktion → neues Ticket (`type: task`) mit `source:`-Verweis.
