# notizbox

Kleine Flask-App zum Erfassen von Notizen. Eine Datei `app.py`, SQLite als
Speicher, keine Nutzerverwaltung. Laeuft lokal auf einem Rechner, wird von
zwei Personen benutzt. Rund 4.000 Notizen im Bestand.

## Stand

- `app.py` — Routen, Templates inline, ~600 Zeilen
- `notizen.db` — SQLite, eine Tabelle `notiz(id, titel, text, angelegt_am)`
- Kein Test, kein Deployment, Start per `python3 app.py`

## Version 2 — was rein soll

Tags an Notizen, Volltextsuche, ein zweiter Rechner soll dieselben Notizen
sehen. Ausserdem soll das Ganze nicht laenger eine 600-Zeilen-Datei sein.

## Offene Entscheidungen

Vor dem ersten Commit an v2 ungeklaert:

1. **Speicher** — bleibt es SQLite (Datei per Sync-Ordner geteilt) oder kommt
   Postgres dazu? SQLite ueber einen Sync-Ordner hat bei uns 2025 schon einmal
   eine Datei zerschossen; Postgres heisst aber, dass auf beiden Rechnern ein
   Dienst laufen muss.
2. **Volltextsuche** — SQLite FTS5, ein `LIKE`-Query, oder eine externe
   Suchmaschine. Haengt an Entscheidung 1.
3. **Tags** — eigene Tabelle mit Verknuepfungstabelle, oder als Textfeld mit
   Komma-Trennung in `notiz`.
4. **Aufteilung von `app.py`** — nach Schichten (routes/services/models) oder
   nach Feature (notizen/, tags/, suche/).
5. **Templates** — inline lassen oder nach `templates/` als Jinja-Dateien.
6. **Migration des Bestands** — 4.000 Notizen: einmaliges Skript, oder
   automatisch beim ersten Start von v2.
7. **Tests** — ueberhaupt welche fuer v2, und wenn ja, wo anfangen.
8. **Name des Zweitrechner-Zugriffs** — direkter Port, Tailscale, oder
   Reverse Proxy mit Basic Auth.
