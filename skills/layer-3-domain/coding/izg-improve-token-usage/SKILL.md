---
name: izg-improve-token-usage
description: Identifiziert Tokenfresser, Redundanzen und ineffiziente Ablaeufe in Skills, Workflows und Skripten, belegt sie mit Messdaten aus den Transcripts und praesentiert sie als HTML-Report.
layer: 3
dependencies: ["grilling", "izg-create-fixplan", "html-report-template"]
disable-model-invocation: true
---

# Improve Token Usage

Findet heraus, wofuer ein Projekt seine Tokens wirklich ausgibt, und schlaegt **Sparmassnahmen** vor. Der Fokus liegt auf **Laufzeitverbrauch** — was waehrend der Arbeit an Tokens verbrannt wird, nicht nur, was beim Laden ins Kontextfenster kommt.

**Scan-Ziel:** die Agent-Konfiguration des Projekts — `.claude/` (sowie `.vibe/`, `.gemini/`, `.codex/`, falls vorhanden): `SKILL.md`-Dateien, `CLAUDE.md`/`AGENTS.md`-Kette, Agents, Hooks, Slash-Commands, MCP-Configs, und die Skripte, die diese aufrufen.

**Abgrenzung zu `context-budget`:** Der `context-budget`-Skill (falls in der Agent-Konfiguration vorhanden) inventarisiert das **statische** Kontextgewicht — Zeilenzahlen, Frontmatter-Bloat, MCP-Tool-Schemata. Dieser Skill baut das nicht nach. Er misst, was im Betrieb passiert: wiederholte Reads, ausufernde Skript-Ausgaben, teure Subagent-Spawns, zerstoerte Caches, Anweisungen, die den Agenten zu unnoetiger Arbeit zwingen.

**Abgrenzung zu `izg-benchmark-actions`:** Dieser Skill misst **retrospektiv**, was in einem Projekt ohnehin schon passiert ist, und sucht darin Tokenfresser. Er vergleicht keine Varianten. Wer wissen will, ob Fassung A eines Ablaufs billiger ist als Fassung B, braucht wiederholte, isolierte Messlaeufe auf derselben Testaufgabe — das macht `izg-benchmark-actions`. Umgekehrt ist dieser Skill das richtige Werkzeug, sobald dort eine Variante verliert und die Ursache gesucht wird.

Vor dem Explore pruefen, ob `context-budget` verfuegbar ist (`~/.claude/skills/context-budget/` oder projektlokal). Wenn ja: dort das statische Inventar holen und im Report referenzieren, statt es selbst zu erheben. Wenn nein: ohne weiterlaufen und im Report vermerken, dass die statische Seite nicht abgedeckt ist.

## Vokabular

Diese Begriffe in jedem Vorschlag exakt so verwenden — nicht in "Performance", "Optimierung" oder "Effizienz" abdriften:

- **Tokenfresser** — eine konkrete Stelle, die messbar Tokens verbraucht (eine Datei, ein Tool-Aufruf, ein Skript, ein Ablauf)
- **Kontextlast** — was ein Tool-Result oder eine Datei ins Kontextfenster kippt
- **Redundanz** — dieselbe Information mehrfach im Kontext (mehrfacher Read derselben Datei, doppelte Regeln in mehreren Configs)
- **Cache-Bruch** — eine Aenderung am Anfang des Kontexts, die den Prefix-Cache invalidiert und alles danach neu kosten laesst
- **Preload vs. Lazy Load** — Inhalt, der immer geladen wird, gegen Inhalt, der erst bei Bedarf gelesen wird
- **Turn-Kosten** — was ein Arbeitsschritt insgesamt kostet, inklusive der Wiederholung des gesamten Kontexts bei jedem Turn
- **Ertrag** — was ein teurer Ablauf inhaltlich zurueckgibt, gemessen an seinen Kosten

## Process

### 1. Messen

Zuerst Zahlen holen, dann lesen. Ohne Messung ist jeder Kandidat eine Vermutung.

```bash
python3 scripts/analyze_transcript.py --project <projektpfad>
```

(Pfad relativ zum Skill-Ordner. `--sessions N` begrenzt auf die N juengsten Sessions, `--json` liefert Rohdaten.)

Das Skript wertet `~/.claude/projects/<projekt-slug>/*.jsonl` aus und liefert:

- **Gesamtverbrauch** — Input, Cache-Schreibvorgang, Cache-Treffer, Output, Cache-Trefferquote
- **Kontextlast pro Tool** — welches Tool wie viel ins Fenster kippt
- **Teuerste Einzelaufrufe** — die konkreten Befehle und Dateien
- **Wiederholte Aufrufe** — dieselbe Datei, derselbe Befehl, mehrfach
- **Subagent-Output** — was in Sidechains verbrannt wurde
- **Genutzte Skills** — welche Skills tatsaechlich aufgerufen wurden

Findet das Skript keine Transcripts, meldet es das und beendet sich mit Exit-Code 1. Dann rein statisch weiterarbeiten und im Report deutlich kennzeichnen, dass die Kandidaten unbelegt sind.

Die Schwellwert-Ableitungen (Cache-Bruch, redundante Aufrufe) stehen nicht mehr hier in Prosa,
sondern werden vom Skript selbst gezogen: Abschnitt "Befunde" im Report bzw. `findings` im
`--json`-Output. Skills, die im Verbrauch nie auftauchen, aber Kontextgewicht haben, sind
Preload-Kandidaten fuer Lazy Load — das kann das Skript mangels Skill-Verzeichnis-Kenntnis noch
nicht pruefen, das bleibt manuell.

### 2. Lesen

Erst jetzt die Konfiguration lesen — gezielt dort, wo die Messung hinzeigt. Fuer die breite Suche das Agent-Tool mit `subagent_type=Explore` nutzen, aber sparsam: ein Skill ueber Tokenverbrauch, der selbst Tokens verschwendet, ist unglaubwuerdig.

Worauf achten:

- **Anweisungen, die Arbeit erzwingen** — "scanne das Repo bei Sessionstart", "lies alle Tickets", "pruefe zuerst X, Y, Z". Jede solche Zeile kostet bei *jeder* Session.
- **Skripte mit ausuferndem Output** — `cat` auf grosse Dateien, unbegrenzte `grep`-Treffer, Debug-Logs im Normalbetrieb. Der Output landet vollstaendig im Kontext.
- **Redundanz zwischen Configs** — dieselbe Regel in globaler `CLAUDE.md`, Projekt-`CLAUDE.md` und einer `SKILL.md`.
- **Grosse SKILL.md-Dateien ohne Referenzsplit** — alles im Preload statt Kernanweisung plus nachgelagerte Referenzdateien.
- **MCP-Server mit vielen Tools**, die im gemessenen Verbrauch nie vorkommen — Schema-Kosten ohne Ertrag.
- **Subagent-Spawns mit schlechtem Ertrag** — teurer Spawn fuer eine Antwort, die ein `grep` geliefert haette.

Jeden Verdacht mit dem **Ertragstest** pruefen: Was gibt diese Stelle inhaltlich zurueck, gemessen an ihren Tokens? Ein "kostet viel, liefert wenig" ist das Signal. Ein grosser Verbrauch mit grossem Ertrag ist kein Kandidat.

### 3. Kandidaten als HTML-Report

Eine eigenstaendige HTML-Datei ins Temp-Verzeichnis des Betriebssystems schreiben, damit nichts im Repo landet. Temp-Verzeichnis aus `$TMPDIR` aufloesen, Fallback `/tmp` (bzw. `%TEMP%` unter Windows), Dateiname `<tmpdir>/token-review-<timestamp>.html`, damit jeder Lauf frisch ist. Danach oeffnen (`xdg-open` unter Linux, `open` unter macOS, `start` unter Windows) und dem User den absoluten Pfad nennen.

Jede Karte enthaelt:

- **Stellen** — welche Dateien, Skripte oder Ablaeufe betroffen sind
- **Messwert** — die konkrete Zahl aus Schritt 1. Ohne Zahl keine Karte, ausser explizit als `Unbelegt` markiert
- **Problem** — warum hier Tokens verbrannt werden
- **Loesung** — was sich aendert, in einfachem Deutsch
- **Ersparnis** — geschaetzte Tokens pro Session oder pro Turn, mit Rechenweg
- **Vorher/Nachher-Visualisierung** — nebeneinander
- **Trade-off-Badge** — `Eindeutig` (kein Nachteil), `Abwaegung` (kostet Faehigkeit, Parallelitaet oder Komfort), `Spekulativ` (Ersparnis unsicher)

Am Ende ein Abschnitt **Groesster Hebel**: welcher Kandidat zuerst, mit Begruendung ueber die Ersparnis.

Details zu Aufbau, Diagrammen und Stil: [HTML-REPORT.md](HTML-REPORT.md).

Noch keine Loesungen ausdetaillieren. Nach dem Schreiben der Datei fragen: "Welchen davon willst du angehen?"

### 4. Grilling — nur bei Abwaegung

Nach der Wahl haengt der naechste Schritt am Badge:

- **`Eindeutig`** → direkt zu Schritt 5. Nicht kuenstlich problematisieren.
- **`Abwaegung` oder `Spekulativ`** → den `/grilling`-Skill aufrufen und durchgehen: Was geht verloren? Wann faellt das auf? Gibt es eine Variante, die den Nachteil vermeidet? Ist die geschaetzte Ersparnis belastbar oder eine Hochrechnung aus einer Session?

Typische Abwaegungen, die ein Grilling verdienen: MCP-Server abschalten (Faehigkeit weg), Skill in Referenzdateien splitten (mehr Reads statt Preload), Subagent-Spawns reduzieren (spart Tokens, kostet Parallelitaet), Anweisungen aus `CLAUDE.md` streichen (spart pro Session, kostet Verlaesslichkeit).

### 5. Fixplan und Ticket

Den `/izg-create-fixplan`-Skill fuer die gewaehlte Massnahme aufrufen. Das Done-Kriterium pro Schritt in Tokens formulieren, nicht in "ist kuerzer" — z. B. *"analyze_transcript.py meldet fuer diesen Ablauf unter 500 Tokens pro Session"*.

Danach ein Ticket anlegen, damit die Umsetzung nachverfolgbar ist:

```bash
bash scripts/tickets.sh new --type refactor --title "<Massnahme>" --by claude
```

Existiert kein Ticketsystem im Zielprojekt (`tickets/` fehlt), den Schritt ueberspringen und dem User den Pfad zur Fixplan-Datei nennen. Nicht ungefragt ein Ticketsystem anlegen.

## Grenzen

- Die Token-Zahlen fuer Tool-Results sind aus der Zeichenlaenge geschaetzt (~4 Zeichen pro Token). Die Werte aus dem `usage`-Feld sind exakt, die pro Tool-Aufruf sind es nicht. So im Report auch benennen.
- Gemessen wird nur, was in den Transcripts steht. Andere Agents (Vibe, Codex, Gemini) schreiben kein kompatibles Format — deren Verbrauch bleibt unsichtbar und muss statisch beurteilt werden.
- Eine einzelne Session ist keine belastbare Basis. Mindestens 3 Sessions auswerten, bevor eine Ersparnis hochgerechnet wird.
