# Tickets

Vollständige Konvention: `~/ai-shared/tickets.md` (auch erreichbar als
`<dein-agent-dir>/tickets.md`).
Bedienung (Flags, Beispiele): Aus dem Repo-Root: `bash scripts/tickets.sh help`.

## Ablauf
1. `bash scripts/tickets.sh list` — erwartet: Tabelle mit offenen/in-progress Tickets.
2. `bash scripts/tickets.sh move <ID> in-progress "<verlaufstext>" --by <agent>` — erwartet: Meldung "... nach in-progress/ verschoben." mit neuem Pfad.
3. Arbeit erledigen.
4. `bash scripts/tickets.sh move <ID> done "<verlaufstext>" --by <agent>` — erwartet: Meldung "... nach done/ verschoben." mit neuem Pfad.

## Wenn etwas fehlschlaegt
| Symptom | Massnahme |
|---|---|
| Platzhalter `{PRJ}` unten im Abschnitt "Prefix" noch nicht ersetzt (z.B. `tickets.sh new` bricht mit "Projekt-Prefix nicht ermittelbar" ab) | `bash scripts/init_tickets.sh <projekt-pfad> <PREFIX>` erneut aufrufen — idempotent, ersetzt den Platzhalter nachtraeglich |
| `scripts/tickets.sh` nicht gefunden | Falsches cwd — ins Repo-Root wechseln (dort liegt `tickets/` neben `scripts/`) |
| `move` schlaegt fehl (z.B. `blocked` -> `in-progress` verboten) | Fehlermeldung des Skripts lesen, erlaubten Statusuebergang pruefen; kein manuelles `mv` als Ersatz |

## Prefix
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Die Zeile oben wird von `init_tickets.sh` mit dem echten Prefix befuellt und dient
danach `scripts/tickets.sh new` als projekt-lokale Laufzeit-Quelle (Zeile wird per Regex
ausgelesen). Vergeben wird das Prefix zentral in der Registry
`~/ai-shared/project-identifier.md`; gelesen wird sie dafuer nicht.

## Lookup-Reihenfolge
Nur auf Ansage suchen: 1. `in-progress/` 2. `open/` 3. `blocked/` (nur bei gezielter
Blocker-Aufloesung). Nie rekursiv über `tickets/` — `done/` ist Jahres-Archiv und
wächst monoton. Details, Frontmatter-Felder, Status-Lifecycle: `tickets.md`.
