# Tickets

Vollständige Konvention: `tickets.md` im globalen Verzeichnis deines AI-Agenten.

## Tickets finden
Nur auf Ansage. Wenn gesucht wird:
1. `in-progress/` — angefangene Arbeit
2. `open/` — nächste Arbeit
3. `blocked/` — nur wenn Blocker gezielt gelöst werden soll

Nie rekursiv über `tickets/` suchen — `done/` ist Archiv (nach Jahr unterteilt) und
wächst monoton. Immer über die aktiven Ordner oder `scripts/tickets.sh` gehen.

## Dateiname
`{PRJ}-T-{NNN}_{kurz-beschreibung}.md`
Der `{PRJ}`-Platzhalter oben wird von `init_tickets.sh` durch das echte Prefix ersetzt
und dient danach `scripts/tickets.sh new` als projekt-lokale Laufzeit-Quelle (Zeile wird
per Regex ausgelesen). Vergeben wird das Prefix zentral in der Registry
`project-identifier.md` im globalen Agent-Verzeichnis; gelesen wird sie dafuer nicht.

## Ticket anlegen
```bash
bash scripts/tickets.sh new --type <bug|task|feature|question> --priority <high|normal|low> \
  --title "<titel>" --by <agent> [--group SLUG] [--assigned AGENT] [--source DOC-ID] [--body TEXT|-]
```
Erzeugt ID, Datei und Frontmatter in einem Kommando, landet in `open/`. `--body -` liest
die Beschreibung von stdin. Nur die naechste ID ohne Ticket: `bash scripts/next_ticket_id.sh {PRJ}`.

## Statuswechsel
```bash
bash scripts/tickets.sh move <ID> <status> "<verlaufstext>" [--by <agent>]
```
Hängt den Verlaufseintrag an, setzt `status:`, verschiebt die Datei — ein Kommando.
Erlaubt: `open|in-progress|blocked|done`; `blocked` → `in-progress` direkt ist verboten
(erst `open`). Alternativ weiterhin von Hand: `status:`-Feld ändern, Verlaufseintrag
pflegen, danach (Codex/Gemini) selbst `bash scripts/tickets.sh sync` aufrufen.
