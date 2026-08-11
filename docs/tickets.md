# Ticketsystem Konvention

> Diese Datei ist die **globale Konventions-Quelle**. Sie liegt im Verzeichnis deines
> AI-Agenten (`~/.claude`, `~/.codex`, `~/.gemini`, `~/.vibe`), wird per
> `scripts/setup_global_conventions.sh` dorthin deployt und in der Agent-Konfig
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
(das Script liegt im globalen Agent-Verzeichnis). Das optionale zweite Argument ist
das Projekt-Prefix — es wird in `tickets/PROTOCOL.md` verankert. Fehlt es, bleibt der
`{PRJ}`-Platzhalter stehen (bei TTY fragt das Script interaktiv nach):
```bash
bash ~/.claude/scripts/init_tickets.sh /pfad/zum/projekt PREFIX
```

```
tickets/
├── PROTOCOL.md     # Projektspezifische Regeln (optional)
├── .counter        # Zähler für Ticket-IDs (nicht manuell editieren)
├── open/
├── in-progress/
├── blocked/
└── done/
    ├── 2026/       # Archiv nach Jahr (created:-Feld), kuenftig 2027/ usw.
    └── ...
```

## Dateiname

```
{PRJ}-T-{NNN}_{kurz-beschreibung}.md
```

`{PRJ}` = Projekt-Prefix aus der Registry `project-identifier.md` im globalen Agent-Verzeichnis.  
Nächste ID immer via Script abfragen — nie manuell zählen:

```bash
bash scripts/next_ticket_id.sh IZG
# → IZG-T-007
```

> `next_ticket_id.sh` liegt **projekt-lokal** (`<projekt>/scripts/`, von
> `init_tickets.sh` erzeugt) — **nicht** im Agent-Dir. Global deployt sind nur
> `init_tickets.sh` und der `ticket-mover`-Hook. `next_ticket_id.sh` delegiert an
> `tickets.sh next` — beide Skripte liegen nebeneinander in `<projekt>/scripts/`.

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

**Groessenkonvention:** Ein Ticket beschreibt **was zu tun ist**, nicht **warum die
Architektur so aussieht**. Richtwert: unter 2 KB. Wird es groesser, steckt meist eine
Entscheidung mit drin, die nach `docs/adr/` gehoert — Verweis dann ueber das
`source:`-Feld im Frontmatter. Pflichtabschnitte bleiben Beschreibung,
Akzeptanzkriterien, Verlauf; optionale Abschnitte wie „Nicht in diesem Ticket" oder
„Blockiert durch" sind erlaubt. Kein Linter, keine Laengenpruefung im Hook — nur
Konvention.

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
- **`status:`-Flip immer als letzten Edit.** Beim Statuswechsel fallen zwei Änderungen an (Verlaufseintrag + `status:`). Den Verlaufseintrag zuerst schreiben, den `status:`-Flip zuletzt — der Hook verschiebt die Datei beim Flip, und danach ist kein weiterer Edit auf dem (neuen) Pfad nötig. Andersherum müsste die verschobene Datei erst neu gelesen werden (kostet Token).
- `blocked/` → immer zurück nach `open/`, nie direkt nach `in-progress/`
- `done/` ist finales Archiv, nicht löschen. Nach Jahr unterteilt (`done/2026/`, künftig
  `done/2027/` usw.) — der Hook legt das Jahr aus `created:` fest (Fallback: aktuelles Jahr)

## Tickets finden

Nur auf Ansage — kein automatischer Scan bei Sessionstart. Der User gibt vor, ob und an
welchem Ticket gearbeitet wird.

`scripts/tickets.sh list` ist der Weg, Tickets zu finden — eine Frontmatter-Zeile pro
Ticket statt N volle Datei-Reads. Ohne `--status` in dieser Reihenfolge, `done/` ausgenommen:
`in-progress` (angefangene Arbeit) → `open` (nächste sinnvolle Arbeit) → `blocked`
(nur wenn gezielt ein Blocker gelöst werden soll):

```bash
bash scripts/tickets.sh list                          # in-progress, open, blocked
bash scripts/tickets.sh list --status done             # Archiv explizit
bash scripts/tickets.sh list --group auth-refactor     # nach Gruppe filtern
bash scripts/tickets.sh list --type bug                # nach Typ filtern
bash scripts/tickets.sh show IZG-T-001                 # volle Ticketdatei, Ordner egal
```

**Nie rekursiv über `tickets/` suchen** (`grep -r`, `find`, Volltext-Read über alle
Unterordner) — `done/` wächst monoton und zahlt sonst bei jeder Abfrage mit. Immer über
die aktiven Ordner (`open/`, `in-progress/`, `blocked/`) oder `tickets.sh` gehen. Einzige
Ausnahme: `tickets.sh next` selbst — der greift shell-seitig rekursiv zu, kostet aber
keinen Token, weil nur die ID als Ausgabe zurückkommt.

## Gruppenabfrage

```bash
bash scripts/tickets.sh list --group auth-refactor
```

## question-Tickets

Werden direkt `done/` sobald die Antwort im Verlauf steht. Ergibt die Antwort eine Folgeaktion → neues Ticket (`type: task`) mit `source:`-Verweis.
