# Tickets

Vollständige Konvention: `~/ai-shared/tickets.md` (auch erreichbar als
`<dein-agent-dir>/tickets.md`).
Bedienung (Flags, Beispiele): Aus dem Repo-Root: `bash scripts/tickets.sh help`.

## Ablauf
1. `bash scripts/tickets.sh list`
2. `bash scripts/tickets.sh move <ID> in-progress "<verlaufstext>" --by <agent>`
3. Arbeit erledigen
4. `bash scripts/tickets.sh move <ID> done "<verlaufstext>" --by <agent>`

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
