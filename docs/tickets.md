# Ticketsystem Konvention

> Diese Datei wird von `scripts/init_tickets.sh` in neue Projekte deployt.
> In `CLAUDE.md` einbinden damit Claude die Konvention bei jedem Session-Start kennt:
> ```markdown
> @docs/tickets.md
> ```

Leichtgewichtiges, file-basiertes Tracking für Bugs, Tasks, Features und Fragen.

## Ablage

`tickets/` liegt immer im **Repo-Root**.

Falls `tickets/` noch nicht existiert (nach Bootstrap liegt das Script lokal):
```bash
bash scripts/init_tickets.sh
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

`{PRJ}` = Projekt-Kürzel aus `docs/doc-ids.md`.  
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
