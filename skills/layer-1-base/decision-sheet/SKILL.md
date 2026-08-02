---
name: decision-sheet
description: "Bündelt viele Entscheidungsfragen in ein Dokument, das der User ausserhalb der CLI in einem HTML-Renderer beantwortet und als Antwort-Datei zurückgibt. Statt zehn AskUserQuestion-Runden ein Sheet. Dieser Skill sollte verwendet werden, wenn mehr als drei Entscheidungen offen sind, wenn der User sie am Stück oder in Ruhe beantworten will (Fragenkatalog, Entscheidungsliste, Sheet, Fragebogen), oder wenn eine exportierte .answers.json eingelesen werden soll."
layer: 1
dependencies: []
status: stable
disable-model-invocation: true
---

# Decision Sheet

Entscheidungsfragen verlassen die CLI: Agent schreibt ein Sheet, der User beantwortet
es im Browser, die Antworten kommen als kompakte JSON zurück.

Drei bewegliche Teile:

| Teil | Wo | Wer |
|------|-----|-----|
| Sheet `<slug>.jsonl` | `<projekt>/.decisions/` | Agent schreibt |
| Renderer `index.html` | im Skill; global gespiegelt nach `~/ai-shared/decision-sheet/` | User bedient |
| Antworten `<slug>.answers.json` | `<projekt>/.decisions/` | User exportiert |

Die Scripts im Skill funktionieren überall — auch auf einem System, auf dem der
globale Setup-Schritt nie gelaufen ist. Die Hooks sind Komfort, keine Voraussetzung:
sie sparen dir pro Sheet ein paar Tool-Calls, mehr nicht. Du musst nicht wissen, ob
sie da sind — die Scripts erkennen es selbst.

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
{"id":6,"q":"Migrations-Skript synchron oder als Job?","t":"pick","o":["synchron","Job"],"ctx":"Bestand: 40k Zeilen in ticket_legacy, Migration lief 2025 zuletzt bei ticket_archive - synchron dauerte dort 6min und blockte den Import."}
```

Danach **immer** diesen einen Befehl — unabhängig davon, ob die Hooks eingerichtet
sind, und egal ob du die Datei per Write, Edit oder Bash-Heredoc angelegt hast:

```bash
python3 <skill>/scripts/render_sheet.py .decisions/<slug>.jsonl
```

Das Script validiert das Sheet (JSON pro Zeile, doppelte ids, fehlende Optionen,
kaputte oder zyklische `dep`-Verweise), baut die HTML und entscheidet dann selbst:

- **Stop-Hook registriert** → es meldet „Fenster geht auf, sobald du fertig
  geantwortet hast" und überlässt das Öffnen dem Hook. Nichts weiter zu tun.
- **Kein Hook** → es öffnet das Fenster sofort.

Bricht es mit einer Fehlermeldung ab: Sheet korrigieren, nicht das Script umgehen.
Der Aufruf ist auch mit Hook kein Leerlauf — er ist deine einzige Rückmeldung, dass
das Sheet überhaupt valide ist, bevor dein Turn endet.

Liegt der Skill nicht im Projekt, tut es der globale Spiegel:
`python3 ~/ai-shared/decision-sheet/render_sheet.py …` — identisches Script.

### Feldreferenz

| Feld | Pflicht | Bedeutung |
|------|---------|-----------|
| `id` | ja | Zahl oder kurzer String, eindeutig |
| `q` | ja | Fragetext, eine Zeile |
| `t` | nein | `pick` (default) · `multi` · `yn` · `text` |
| `o` | bei `pick`/`multi` | Optionen. Bei `yn` implizit ja/nein |
| `d` | nein | **Empfehlung** — im Renderer vorausgewählt und als `EMPF` markiert. Bei `yn`: `"y"`/`"n"`. Bei `multi`: Array |
| `why` | nein | Eine Zeile Begründung/Trade-off unter der Frage |
| `ctx` | nein | Längerer Hintergrund zu **dieser einen Frage** — im Renderer eingeklappt hinter „+ Kontext", nicht standardmäßig sichtbar. Nicht zu verwechseln mit dem Header-`ctx` (Dokumentverweis fürs ganze Sheet) |
| `dep` | nein | `[id, wert]` oder `[id, [wert1, wert2]]` — Frage wird nur aktiv, wenn die andere so beantwortet ist |

Header: `v` (Format-Version, aktuell 1), `sheet` (Slug = Dateiname ohne Endung),
`title`, `ctx` (Pfad zum Dokument mit dem Hintergrund, optional).

### Regeln beim Schreiben

1. **Immer ein `d` setzen, wenn du eine Meinung hast.** Das ist der Punkt des
   Formats: der User bestätigt schweigend und beantwortet nur, wo er abweicht.
   Nur bei echt offenen Fragen (Namen, Zahlen, Präferenzen) `d` weglassen — die
   markiert der Renderer als „offen".
2. **`why` nur wenn es das Trade-off wirklich klärt.** Eine Zeile, kein Absatz.
   Braucht eine Frage mehr Hintergrund als eine Zeile — z.B. weil sie ohne
   Projekt-Detail (Bestandsgröße, letzter Vorfall, betroffene Komponente) nicht
   beantwortbar ist — gehört der in das Fragen-`ctx`, nicht in `why` gequetscht.
   Frage bleibt dadurch kurz, der Kontext ist trotzdem einen Klick entfernt statt
   in `why` aufgebläht oder ganz weggelassen.
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

**Kommt auf `#answers` nichts zurück**, ist der Hook auf diesem System nicht
eingerichtet. Dann holst du die Datei selbst — dasselbe Script, das der Hook aufruft:

```bash
python3 <skill>/scripts/fetch_answers.py [--slug <slug>]
```

Sag dem User in dem Fall einmal, dass er dir nach dem Export kurz Bescheid gibt,
statt auf die Automatik zu warten.

Format:

```json
{"sheet":"ticketsystem-v2","a":{"1":"Timestamp","3":"archive","4":["claude","codex","vibe"],"5":{"a":"flock","n":"prüf ob NFS ein Problem ist"}}}
```

Interpretation:

- **Key fehlt** → Empfehlung (`d`) übernommen. `"a": {}` heisst: alles wie vorgeschlagen.
- **Wert** → die abweichende Antwort. Bei `multi` ein Array; `[]` heisst „nichts davon"
  und ist eine echte Antwort, kein leerer Eintrag.
- **`{"a": wert, "n": "notiz"}`** → Antwort plus Ergänzung des Users. Die Notiz ist
  verbindlich, nicht Deko — sie enthält oft die eigentliche Einschränkung.
- **`{"a": null, "n": "notiz"}`** → keine Auswahl, nur ein Kommentar. Meist eine
  Rückfrage, die du beantworten musst, bevor du die Entscheidung umsetzt.
- Fragen, deren `dep` nicht erfüllt war, tauchen nicht auf — die sind gegenstandslos.

Die Notiz steht bewusst im Objekt und nicht als `[wert, notiz]`-Tupel: eine
`multi`-Antwort mit zwei Optionen (`["claude","codex"]`) wäre sonst nicht von
Antwort-plus-Notiz zu unterscheiden.

Falls das Sheet nicht mehr im Kontext ist (Kompaktierung), liegt es als
`.decisions/<slug>.jsonl` daneben — lesen statt raten. Antwort-Dateien tragen bewusst
keine Fragetexte mit, damit der Rückweg billig bleibt.

Nach dem Umsetzen: `.decisions/` gehört in die `.gitignore` des Projekts, die Sheets
sind Wegwerf-Artefakte. Was dauerhaft gilt, gehört als ADR (`doc-ids`) oder in
`CONTEXT.md` — nicht ins Sheet.

---

## Setup

**Pro Projekt: nichts.** `.decisions/` wird beim ersten Sheet angelegt und gehört in
die `.gitignore`. Der Skill-Pull bringt alles mit, was der Ablauf braucht —
`assets/index.html`, `scripts/`, `hooks/`.

**Global: optional, aber empfohlen.** Ein Schritt, einmal pro Maschine:

```bash
bash <ai-SKILL-set>/scripts/setup_global_conventions.sh ~/.claude
```

Spiegelt Renderer und Scripts nach `~/ai-shared/decision-sheet/` und registriert zwei
Hooks in `~/.claude/settings.json`:

| Hook | Event | Wirkung |
|------|-------|---------|
| `decision-sheet-open.sh` | `Stop` | neu geschriebenes, unbeantwortetes Sheet geht von selbst auf |
| `decision-answers.sh` | `UserPromptSubmit` | `#answers` holt die Antworten zurück |

Was die Hooks bringen: der Hinweg funktioniert auch dann, wenn das Sheet an
`render_sheet.py` vorbei entstanden ist, und der Rückweg kostet dich keinen Tool-Call.
Ohne sie läuft alles gleich, nur mit zwei bis drei Aufrufen mehr pro Sheet.

### Ohne globales Setup — und andere Agents (Codex, Vibe, Gemini)

Die Hooks sind Claude-spezifisch, das Format und die Scripts sind es nicht. Der
komplette Ablauf funktioniert aus dem gepullten Skill heraus:

1. Sheet nach `.decisions/<slug>.jsonl` schreiben (identisches Format).
2. `python3 <skill>/scripts/render_sheet.py .decisions/<slug>.jsonl` — findet keinen
   Hook, öffnet das Fenster also selbst. Fehlt der globale Spiegel, fällt das Script
   auf die `assets/index.html` neben sich zurück.
3. Nach dem Export `python3 <skill>/scripts/fetch_answers.py` — holt die Datei aus
   dem Download-Ordner nach `.decisions/` und gibt sie aus (Interpretation: Modus 2).

## Wenn etwas nicht funktioniert

| Symptom | Ursache |
|---------|---------|
| Script meldet „Stop-Hook aktiv", aber es geht kein Fenster auf | `.decisions/.opened` hat das Sheet schon gestempelt (Sheet anfassen ändert die mtime), oder der Hook steht zwar in `settings.json`, ist aber nicht ausführbar |
| Sheet geschrieben, gar nichts passiert | `render_sheet.py` nicht aufgerufen — genau dafür ist der Aufruf Pflicht, auch mit Hook |
| `render_sheet.py`: keine index.html gefunden | Skill unvollständig gepullt (`assets/` fehlt) und kein globaler Spiegel da |
| Renderer zeigt Dropzone statt Fragen | Sheet defekt — Fehlermeldung steht in der Box darunter |
| `#answers` bringt nichts | Hook nicht eingerichtet → `fetch_answers.py` selbst aufrufen; oder Export noch nicht gespeichert (nur „Kopieren" gedrückt) |
| Export ist `{"sheet":…,"a":{}}` | Kein Fehler — der User hat alle Empfehlungen übernommen |

Letzter Ausweg ganz ohne Scripts: `assets/index.html` im Browser öffnen, Sheet
reinziehen, exportierte Datei selbst nach `.decisions/` legen und den Pfad nennen.
