# Messaufbau izg-decision-sheet

Gemessen mit `izg-benchmark-actions`. Frage: **Lohnt der Skill gegenueber dem,
was das Modell ohne ihn tut?**

| Teil | Datei |
|------|-------|
| Testaufgabe | `aufgabe.md` (Pruefsumme im Messplan) |
| Messprojekt (Vorlage) | `projekt/` |
| Messprojekt (Arbeitskopie) | `~/.local/share/izg-bench/projekte/notizbox` |
| Varianten | `setup-ohne-skill.sh`, `setup-mit-skill.sh` |

## Warum ein eigenes Messprojekt

`claude` laedt jede `CLAUDE.md` oberhalb des Arbeitsverzeichnisses. Gemessen
wird deshalb ausserhalb von `ai-SKILL-set` — dessen `CLAUDE.md` ("Stop. Read
this before scanning the repo.") wuerde jeden Lauf in eine Rueckfrage kippen.
`projekt/` ist die versionierte Vorlage, `init.sh` legt die Arbeitskopie an.

## Einmalig

```bash
bash init.sh
```

## Messrunde

`PATH` mit dem `shim/` davor: das no-op `xdg-open` verhindert, dass pro Lauf
ein Browserfenster aufgeht. Beide Varianten laufen damit, die Messung bleibt fair.

```bash
BENCH=~/Dokumente/AI/ai-SKILL-set/skills/layer-3-domain/coding/izg-benchmark-actions
HIER=~/Dokumente/AI/ai-SKILL-set/skills/layer-1-base/izg-decision-sheet/benchmark

PATH="$HIER/shim:$PATH" python3 $BENCH/scripts/bench.py run \
  --task izg-decision-sheet --variant ohne-skill --repeat 3 \
  --prompt-file $HIER/aufgabe.md \
  --project ~/.local/share/izg-bench/projekte/notizbox \
  --model sonnet --permission-mode bypassPermissions \
  --setup "bash $HIER/setup-ohne-skill.sh"

PATH="$HIER/shim:$PATH" python3 $BENCH/scripts/bench.py run \
  --task izg-decision-sheet --variant mit-skill --repeat 3 \
  --setup "bash $HIER/setup-mit-skill.sh"

python3 $BENCH/scripts/bench.py compare --task izg-decision-sheet --baseline ohne-skill
```

Der zweite `run` kommt ohne die uebrigen Optionen aus — die stehen ab dem
ersten Lauf im Messplan (`~/.local/share/izg-bench/plans/izg-decision-sheet.json`).

## Ertrag bewerten

Kriterien **vor** der Messung festgelegt. `ok` nur, wenn der Lauf alles davon liefert:

1. Alle acht offenen Entscheidungen aus `CONTEXT.md` sind abgedeckt.
2. Sie liegen **an einer Stelle** vor, am Stueck beantwortbar — nicht als
   Kette von Rueckfragen und nicht als Fliesstext, in dem die Fragen stecken.
3. Zu jeder Frage steht eine Empfehlung dabei.
4. Die Abhaengigkeit "Volltextsuche haengt an Speicher" ist als solche kenntlich.
5. Am Repo/Projekt wurde nichts ausser der Fragenvorlage veraendert.

Fehlt eines davon: `partial`. Aufgabe verfehlt oder Lauf haengt in Rueckfragen: `fail`.

```bash
python3 $BENCH/scripts/bench.py judge --task izg-decision-sheet \
  --variant mit-skill --run 1 --outcome ok
```

## Bekannte Verzerrungen

- Die beiden Hooks (`Stop`, `UserPromptSubmit`) sind global registriert und
  bleiben in beiden Varianten aktiv. Gemessen wird die Wirkung der `SKILL.md`,
  nicht die der Hooks.
- `claude -p` ist headless: `AskUserQuestion` fuehrt dort ins Leere. Die
  Variante ohne Skill weicht deshalb auf eine Datei oder den Antworttext aus —
  das ist der realistische Vergleichsfall, aber kein Beleg dafuer, wie teuer
  interaktives Nachfragen im Dialog waere.
- `--permission-mode bypassPermissions`, weil der Ablauf schreiben und
  `render_sheet.py` starten muss. Gilt fuer beide Varianten.
