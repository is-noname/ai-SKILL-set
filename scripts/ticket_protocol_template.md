# Tickets

Vollständige Konvention: `tickets.md` im globalen Verzeichnis deines AI-Agenten.
Bedienung (Flags, Beispiele): `bash scripts/tickets.sh help`.

## Prefix
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Der `{PRJ}`-Platzhalter oben wird von `init_tickets.sh` durch das echte Prefix ersetzt
und dient danach `scripts/tickets.sh new` als projekt-lokale Laufzeit-Quelle (Zeile wird
per Regex ausgelesen). Vergeben wird das Prefix zentral in der Registry
`project-identifier.md` im globalen Agent-Verzeichnis; gelesen wird sie dafuer nicht.

## Lookup-Reihenfolge
Nur auf Ansage suchen: 1. `in-progress/` 2. `open/` 3. `blocked/` (nur bei gezielter
Blocker-Aufloesung). Nie rekursiv über `tickets/` — `done/` ist Jahres-Archiv und
wächst monoton. Details, Frontmatter-Felder, Status-Lifecycle: `tickets.md`.
