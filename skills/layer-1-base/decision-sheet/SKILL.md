---
name: decision-sheet
description: "Bündelt viele Entscheidungsfragen in ein Dokument, das der User ausserhalb der CLI in einem HTML-Renderer beantwortet und als Antwort-Datei zurückgibt. Statt zehn AskUserQuestion-Runden ein Sheet. Dieser Skill sollte verwendet werden, wenn mehr als drei Entscheidungen offen sind, wenn der User sie am Stück oder in Ruhe beantworten will (Fragenkatalog, Entscheidungsliste, Sheet, Fragebogen), oder wenn eine exportierte .answers.json eingelesen werden soll."
layer: 1
dependencies: []
status: prototype
disable-model-invocation: true
---

# Decision Sheet

Entscheidungsfragen verlassen die CLI: Agent schreibt ein Sheet, der User beantwortet
es im Browser, die Antworten kommen als kompakte JSON zurück.

Drei bewegliche Teile:

| Teil | Wo | Wer |
|------|-----|-----|
| Sheet `<slug>.jsonl` | `<projekt>/.decisions/` | Agent schreibt |
| Renderer `index.html` | `~/ai-shared/decision-sheet/` (global, einmal pro Maschine) | User bedient |
| Antworten `<slug>.answers.json` | `<projekt>/.decisions/` | User exportiert |

Der Renderer-Pfad ist **Konvention, nicht Suchergebnis** — nicht danach suchen.
Fehlt er, ist der globale Setup-Schritt nicht gelaufen (siehe unten).

## Wann dieser Skill statt AskUserQuestion

Ab etwa vier offenen Entscheidungen, oder sobald Fragen voneinander abhängen
(`dep`). Bei einer oder zwei Fragen ist AskUserQuestion schneller.

---

## Modus 1: Sheet schreiben

`.decisions/<slug>.jsonl` anlegen — ein JSON-Objekt pro Zeile, erste Zeile Header:

```
{"v":1,"sheet":"ticketsystem-v2","title":"Ticketsystem v2","ctx":"docs/RFC-20260727-001.md"}
{"id":1,"q":"IDs per Counter oder Timestamp?","t":"pick","o":["Counter","Timestamp","beides"],"d":"Counter","why":"kollisionsfrei, braucht aber Lockfile"}
{"id":2,"q":"Prefix-Registry global lassen?","t":"yn","d":"y"}
{"id":3,"q":"Wie soll der Archiv-Ordner heissen?","t":"text","d":"archiv"}
{"id":4,"q":"Welche Agents dürfen Tickets schreiben?","t":"multi","o":["claude","codex","gemini","vibe"],"d":["claude","codex"]}
{"id":5,"q":"Lock via flock oder mkdir?","t":"pick","o":["flock","mkdir"],"dep":[1,"Counter"]}
```

**Öffnen musst du nichts.** Der `Stop`-Hook rendert das Sheet und öffnet das Fenster,
sobald du fertig geredet hast — egal ob du die Datei per Write, Edit oder Bash-Heredoc
angelegt hast. Also: Sheet schreiben, Antwort abschließen, fertig.

Nur wenn der Hook nicht greift (anderer Agent, kein `settings.json`), von Hand:

```bash
python3 ~/ai-shared/decision-sheet/render_sheet.py .decisions/<slug>.jsonl
```

(Der skill-lokale `scripts/render_sheet.py` funktioniert identisch und fällt auf die
`assets/index.html` daneben zurück — nutze ihn nur, wenn der globale Pfad fehlt.)

Das Script validiert das Sheet (JSON pro Zeile, doppelte ids, fehlende Optionen,
kaputte `dep`-Verweise), injiziert es in eine Kopie der `index.html` und öffnet sie.
Bricht es mit einer Fehlermeldung ab: Sheet korrigieren, nicht das Script umgehen.

### Feldreferenz

| Feld | Pflicht | Bedeutung |
|------|---------|-----------|
| `id` | ja | Zahl oder kurzer String, eindeutig |
| `q` | ja | Fragetext, eine Zeile |
| `t` | nein | `pick` (default) · `multi` · `yn` · `text` |
| `o` | bei `pick`/`multi` | Optionen. Bei `yn` implizit ja/nein |
| `d` | nein | **Empfehlung** — im Renderer vorausgewählt und als `EMPF` markiert. Bei `yn`: `"y"`/`"n"`. Bei `multi`: Array |
| `why` | nein | Eine Zeile Begründung/Trade-off unter der Frage |
| `dep` | nein | `[id, wert]` oder `[id, [wert1, wert2]]` — Frage wird nur aktiv, wenn die andere so beantwortet ist |

Header: `v` (Format-Version, aktuell 1), `sheet` (Slug = Dateiname ohne Endung),
`title`, `ctx` (Pfad zum Dokument mit dem Hintergrund, optional).

### Regeln beim Schreiben

1. **Immer ein `d` setzen, wenn du eine Meinung hast.** Das ist der Punkt des
   Formats: der User bestätigt schweigend und beantwortet nur, wo er abweicht.
   Nur bei echt offenen Fragen (Namen, Zahlen, Präferenzen) `d` weglassen — die
   markiert der Renderer als „offen".
2. **`why` nur wenn es das Trade-off wirklich klärt.** Eine Zeile, kein Absatz.
   Braucht eine Frage mehr Kontext, gehört der in das Dokument hinter `ctx`.
3. **Eine Zeile pro Frage, kein Pretty-Print.** Zeilenumbrüche im JSON zerstören
   den Parser (ein Objekt = eine Zeile ist die einzige Regel des Formats).
4. **Fragen sortieren:** grundlegende zuerst, Folgefragen per `dep` dahinter.
   Nie eine `dep`-Frage vor der Frage, an der sie hängt.
5. **Keine Fragen stellen, die du selbst entscheiden kannst.** Ein Sheet mit 20
   Trivialitäten ist schlimmer als drei gute Fragen in der CLI.
6. **Bei `multi` keine „keine/reicht so"-Pseudo-Option.** Nichts ausgewählt bedeutet
   dort schon „keine" — eine zusätzliche Verneinungs-Option macht das Ergebnis
   zweideutig (leeres Array vs. abgewählte Pseudo-Option lesen sich gleich).
   Wenn „nichts davon" eine echte Antwort ist, gehört die Frage als `yn` davor.

---

## Modus 2: Antworten lesen

Der User tippt `#answers` im Chat. Der `UserPromptSubmit`-Hook holt die neueste
`*.answers.json` aus dem Download-Ordner, verschiebt sie nach `.decisions/` und
legt den Inhalt in den Kontext. Optional mit Slug: `#answers ticketsystem-v2`.

Format:

```json
{"sheet":"ticketsystem-v2","a":{"1":"Timestamp","3":"archive","4":["claude","codex","vibe"],"5":["flock","prüf ob NFS ein Problem ist"]}}
```

Interpretation:

- **Key fehlt** → Empfehlung (`d`) übernommen. `"a": {}` heisst: alles wie vorgeschlagen.
- **Wert** → die abweichende Antwort.
- **`[wert, notiz]`** → Antwort plus Ergänzung des Users. Die Notiz ist verbindlich,
  nicht Deko — sie enthält oft die eigentliche Einschränkung.
- **`[null, notiz]`** → keine Auswahl, nur ein Kommentar. Meist eine Rückfrage,
  die du beantworten musst, bevor du die Entscheidung umsetzt.
- Fragen, deren `dep` nicht erfüllt war, tauchen nicht auf — die sind gegenstandslos.

Falls das Sheet nicht mehr im Kontext ist (Kompaktierung), liegt es als
`.decisions/<slug>.jsonl` daneben — lesen statt raten. Antwort-Dateien tragen bewusst
keine Fragetexte mit, damit der Rückweg billig bleibt.

Nach dem Umsetzen: `.decisions/` gehört in die `.gitignore` des Projekts, die Sheets
sind Wegwerf-Artefakte. Was dauerhaft gilt, gehört als ADR (`doc-ids`) oder in
`CONTEXT.md` — nicht ins Sheet.

---

## Setup

**Global, einmal pro Maschine** — deployt Renderer und Hook:

```bash
bash <ai-SKILL-set>/scripts/setup_global_conventions.sh ~/.claude
```

Legt `~/ai-shared/decision-sheet/{index.html,render_sheet.py}` an und registriert zwei
Hooks in `~/.claude/settings.json`:

| Hook | Event | Wirkung |
|------|-------|---------|
| `decision-sheet-open.sh` | `Stop` | neu geschriebenes, unbeantwortetes Sheet geht auf |
| `decision-answers.sh` | `UserPromptSubmit` | `#answers` holt die Antworten zurück |

**Pro Projekt:** nichts. `.decisions/` wird beim ersten Sheet angelegt.

### Andere Agents (Codex, Vibe, Gemini)

Die Hooks sind Claude-spezifisch, das Format ist es nicht. Für die anderen Agents
liegen Renderer und Script trotzdem unter `~/ai-shared/decision-sheet/` — der
komplette Ablauf funktioniert manuell:

1. Sheet nach `.decisions/<slug>.jsonl` schreiben (identisches Format).
2. `python3 ~/ai-shared/decision-sheet/render_sheet.py .decisions/<slug>.jsonl` —
   öffnet das Fenster selbst, kein Hook nötig.
3. Der User speichert die Antworten und nennt den Pfad; die
   `<slug>.answers.json` direkt lesen (Interpretation siehe Modus 2).

## Wenn etwas nicht funktioniert

| Symptom | Ursache |
|---------|---------|
| Sheet geschrieben, kein Fenster geht auf | Stop-Hook fehlt in `settings.json`, oder `.decisions/.opened` hat es schon gestempelt (Sheet anfassen ändert die mtime) |
| `render_sheet.py`: keine index.html gefunden | globaler Setup-Schritt fehlt |
| Renderer zeigt Dropzone statt Fragen | Sheet defekt — Fehlermeldung steht in der Box darunter |
| `#answers` bringt nichts | Hook nicht in `settings.json`, oder Export noch nicht gespeichert (nur „Kopieren" gedrückt) |
| Export ist `{"sheet":…,"a":{}}` | Kein Fehler — der User hat alle Empfehlungen übernommen |

Manueller Weg ohne Hook: Renderer aus `~/ai-shared/decision-sheet/index.html` öffnen,
Sheet reinziehen, exportierte Datei selbst nach `.decisions/` legen und den Pfad nennen.
