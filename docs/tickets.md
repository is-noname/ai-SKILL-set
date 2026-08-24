# Ticketsystem Konvention

> Diese Datei ist die **globale Konventions-Quelle** (deployt per
> `scripts/setup_global_conventions.sh` nach `~/.claude`, `~/.codex`, `~/.gemini`,
> `~/.vibe`, eingebunden in der Agent-Konfig via `@tickets.md`). Projekte tragen keine
> eigene Kopie — ihre `tickets/PROTOCOL.md` verweist hierher.
>
> Beschrieben wird die **Konvention** (Felder, Regeln) — was `tickets.sh` nicht selbst
> sagen kann. Flags, Optionen, Beispielaufrufe: `tickets.sh help`. Interna (ID-Vergabe,
> Status-Hook, Bootstrap-Ebenen): `docs/ticketsystem-architektur.md`.

Leichtgewichtiges, file-basiertes Tracking für Bugs, Tasks, Features und Fragen.

## Ablage

`tickets/` liegt immer im **Repo-Root**. Bootstrap, falls noch nicht vorhanden
(Prefix als zweites Argument, sonst bleibt `{PRJ}` stehen):
```bash
# <AGENT_DIR>: dein eigener Agent-Ordner, z.B. ~/.claude, ~/.codex, ~/.gemini, ~/.vibe
bash <AGENT_DIR>/scripts/init_tickets.sh /pfad/zum/projekt PREFIX
```

Fehlt `init_tickets.sh` dort, ist der globale Bootstrap fuer diesen Agenten noch nicht
gelaufen: `bash scripts/setup_global_conventions.sh <AGENT_DIR>` im `ai-SKILL-set`-Repo.

```
tickets/
├── PROTOCOL.md     # Projektspezifische Regeln (optional)
├── .counter        # Zähler für Ticket-IDs (nicht manuell editieren)
├── open/
├── in-progress/
├── blocked/
└── done/
    └── 2026/       # Archiv nach Jahr (created:-Feld), kuenftig 2027/ usw.
```

## Dateiname

```
{PRJ}-T-{NNN}_{kurz-beschreibung}.md
```

`{PRJ}` wird zur Laufzeit aus `tickets/PROTOCOL.md` des Projekts gelesen (dort von
`init_tickets.sh` verankert). Vergeben wird das Prefix zentral in der Registry
`~/ai-shared/project-identifier.md`.

**Standardweg zum Anlegen:** `scripts/tickets.sh new` — Flags/Beispiel: `tickets.sh help`.

## Frontmatter

| Feld | Pflicht | Werte |
|------|---------|-------|
| `id` | ja | `{PRJ}-T-{NNN}` |
| `title` | ja | Kurze Beschreibung |
| `type` | ja | `bug` / `task` / `feature` / `question` |
| `status` | ja | `open` / `in-progress` / `blocked` / `done` — bestimmt den Ordner, siehe [Status-Lifecycle](#status-lifecycle) |
| `priority` | ja | `high` / `normal` / `low` |
| `created` | ja | `YYYY-MM-DD` |
| `created-by` | ja | `claude` / `gemini` / `codex` / `me` |
| `assigned` | nein | `claude` / `gemini` / `codex` / `me` |
| `started` | nein | `YYYY-MM-DD` — Datum des Wechsels nach `in-progress/` |
| `group` | nein | Slug der zusammengehörige Tickets bündelt |
| `source` | nein | Dokument das das Ticket ausgelöst hat |

`tickets.sh new` setzt die Pflichtfelder automatisch und die optionalen nur bei
uebergebenem Flag — diese Tabelle bleibt Referenz fuer die Feldbedeutung.

## Ticket-Body

Pflichtabschnitte: `## Beschreibung`, `## Akzeptanzkriterien` (Checkbox-Liste),
`## Verlauf` (Eintraege als `### YYYY-MM-DD – agent`, Text darunter).

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

**Standardweg:** `scripts/tickets.sh move <ID> <status> "<verlaufstext>" [--by <agent>]`
— loest die ID auf, haengt den Verlaufseintrag an, setzt `status:`, ruft `sync_one` auf.
Flags/Beispiel: `tickets.sh help`.

**Regeln:**
- Der manuelle Zwei-Edit-Weg (Verlaufseintrag, dann `status:`-Feld) funktioniert weiter —
  `move` ist additiv. Verschiebe-Logik liegt in beiden Fällen in `tickets.sh sync`
  (Reconcile `status:` <-> Ordner). Automatisch nur bei Claude/Vibe (Hook); Codex/Gemini
  rufen `tickets.sh sync` danach selbst auf. Niemals manuell `mv`.
- Jeder Statuswechsel erfordert einen Verlaufseintrag.
- `blocked/` → immer zurück nach `open/`, nie direkt nach `in-progress/`.
- `done/` ist finales Archiv, nicht löschen. Nach Jahr unterteilt (`created:`-Feld,
  Fallback: aktuelles Jahr).

## Ablauf Ticketbearbeitung

1. Tickets finden: `bash scripts/tickets.sh list`
2. In Bearbeitung nehmen: `bash scripts/tickets.sh move <ID> in-progress "<verlaufstext>" --by <agent>`
3. Arbeit erledigen (Akzeptanzkriterien abhaken)
4. Abschliessen: `bash scripts/tickets.sh move <ID> done "<verlaufstext>" --by <agent>`

## Tickets finden

Nur auf Ansage — kein automatischer Scan bei Sessionstart. Der User gibt vor, ob und an
welchem Ticket gearbeitet wird.

`tickets.sh list` ist der Weg, Tickets zu finden — eine Frontmatter-Zeile pro Ticket statt
N volle Datei-Reads. Ohne `--status` in dieser Reihenfolge, `done/` ausgenommen:
`in-progress` (angefangene Arbeit) → `open` (nächste sinnvolle Arbeit) → `blocked` (nur
wenn gezielt ein Blocker gelöst werden soll). Flags/Beispiele: `tickets.sh help`.

**Nie rekursiv über `tickets/` suchen** (`grep -r`, `find`, Volltext-Read über alle
Unterordner) — `done/` wächst monoton und zahlt sonst bei jeder Abfrage mit. Immer über
die aktiven Ordner oder `tickets.sh` gehen. Ausnahme: `tickets.sh next` selbst greift
shell-seitig rekursiv zu, kostet aber keinen Token — nur die ID kommt zurück.

## question-Tickets

Werden direkt `done/` sobald die Antwort im Verlauf steht. Ergibt die Antwort eine Folgeaktion → neues Ticket (`type: task`) mit `source:`-Verweis.
