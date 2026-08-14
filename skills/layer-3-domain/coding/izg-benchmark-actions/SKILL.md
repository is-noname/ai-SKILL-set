---
name: izg-benchmark-actions
description: Vergleicht die Kosten mehrerer Varianten eines Ablaufs — mit oder ohne Skill, alte gegen neue Fassung, Subagent gegen Direktarbeit — durch wiederholte, isolierte Messlaeufe auf derselben Testaufgabe und faellt ein belegtes Urteil. Haelt die Messung als Messplan fest, damit sie nach jeder Optimierungsrunde wiederholbar bleibt.
layer: 3
dependencies: ["izg-transcript-reader"]
disable-model-invocation: true
---

# Benchmark Actions

Stellt **Varianten eines Ablaufs** gegeneinander und beantwortet eine einzige Frage: *Welche Variante loest dieselbe Aufgabe billiger, ohne beim Ertrag zu verlieren?*

Ein Ablauf ist alles, was sich als Prompt ausloesen laesst: ein Skill, ein Slash-Command, eine Workflow-Kette, eine Formulierung in `CLAUDE.md`, ein Subagent-Muster.

**Abgrenzung zu `izg-improve-token-usage`:** Der misst **retrospektiv** ein ganzes Projekt und sucht Tokenfresser — was ist im Betrieb schon passiert. Dieser Skill misst **prospektiv** einzelne Laeufe, die er selbst ausloest, und vergleicht sie. Kein HTML-Report voller Sparkandidaten, kein Fixplan, kein Ticket — am Ende steht eine Tabelle und ein Urteil. Verliert eine Variante, ist *danach* `izg-improve-token-usage` das richtige Werkzeug, um herauszufinden warum.

## Vokabular

- **Testaufgabe** — der identische Prompt, den alle Varianten bearbeiten. Die Konstante des Versuchs
- **Variante** — eine der verglichenen Fassungen (`ohne-skill`, `mit-skill`, `v2`)
- **Lauf** — eine einzelne Ausfuehrung einer Variante, mit eigener Session-ID
- **Gewichtete Tokens** — Verbrauch in Input-Token-Aequivalenten (siehe unten). Die Vergleichsgroesse
- **Spanne** — Minimum bis Maximum ueber die Laeufe einer Variante. Ohne Spanne kein Urteil
- **Ertrag** — hat der Lauf die Testaufgabe geloest: `ok`, `partial`, `fail`
- **Basis** — die Variante, gegen die verglichen wird
- **Urteil** — guenstiger/teurer um X %, oder "kein belastbarer Unterschied"
- **Messrunde** — alle Laeufe, die zu einem Zeitpunkt unter derselben Umgebung entstanden sind. Nur innerhalb einer Runde wird geurteilt
- **Messplan** — die festgehaltene Definition einer Messung (Testaufgabe, Projekt, Modell, Umschaltkommandos). Macht sie Monate spaeter wiederholbar

Nicht in "Performance", "Benchmark-Score" oder "Effizienz" abdriften. Es gibt keine Punktzahl, nur Kosten und Ertrag.

## Warum gewichtet

Rohe Tokensummen bestrafen Varianten, die den Cache gut nutzen. Verglichen wird deshalb in Input-Token-Aequivalenten, angelehnt an die Preisstruktur:

`input x1 + cache_creation x1,25 + cache_read x0,1 + output x5`

Die Gewichte stehen in `scripts/bench.py` (`WEIGHTS`) und werden im Report mit ausgewiesen. Wer sie aendert, macht alte Laufdaten unvergleichbar — dann neu messen.

## Process

### 1. Testaufgabe festlegen

Eine Aufgabe, alle Varianten. Sie muss:

- **realistisch** sein — die Arbeit, um die es wirklich geht, kein Spielzeug
- **abschliessbar** sein — der Lauf endet von selbst, kein offener Dialog
- **pruefbar** sein — man kann hinterher sagen, ob sie geloest wurde

Als Datei ablegen und mit `--prompt-file` verwenden. Nie pro Variante umformulieren; eine geaenderte Testaufgabe macht den Vergleich wertlos. Das Skript merkt sich ihre Pruefsumme und verweigert das Urteil, wenn zwei Fassungen im Spiel sind — auch Monate spaeter.

Die Datei gehoert **neben den Skill, den sie misst**, nicht ins temporaere Verzeichnis. Sie ist der teuerste Teil der Messung: ohne sie faengt jede spaetere Runde bei null an.

### 2. Varianten und Umschaltung festlegen

Fuer jede Variante muss klar sein, wie der Zustand hergestellt wird. Das gehoert in `--setup` (Shell-Kommando, laeuft vor jedem Lauf im Projektverzeichnis):

```bash
--setup "cp variants/mit-skill/SKILL.md .claude/skills/foo/SKILL.md"
--setup "git checkout v2 -- .claude/"
```

Ohne `--setup` misst man dreimal denselben Zustand. Nach dem letzten Lauf den Ausgangszustand wiederherstellen.

**Skills mit `disable-model-invocation: true`** zieht das Modell nicht von selbst. Da die Testaufgabe fuer alle Varianten identisch ist und den Skill nicht nennen darf, muss das Setup die Zeile beim Einspielen entfernen — sonst misst man zweimal die Variante ohne Skill und merkt es nicht:

```bash
--setup "cp -r varianten/mit-skill .claude/skills/foo && sed -i '/^disable-model-invocation:/d' .claude/skills/foo/SKILL.md"
```

Nach dem ersten Lauf im Laufdatensatz unter `skills_used` nachsehen, ob der Skill tatsaechlich gezogen wurde.

**Isolation statt Segmentierung:** Jeder Lauf bekommt eine eigene Session-ID und damit ein eigenes Transcript. Nichts wird nachtraeglich aus einer laufenden Session herausgerechnet.

### 3. Laeufe ausfuehren

Jeder Lauf kostet echtes Geld. **Vor dem ersten `run` dem User die Rechnung nennen** — Anzahl Varianten x `--repeat` — und bestaetigen lassen.

```bash
python3 scripts/bench.py --out /tmp/izg-bench run \
  --task ticket-anlegen --variant ohne-skill \
  --prompt-file aufgabe.md --repeat 3 \
  --project /pfad/zum/projekt --setup "..." --permission-mode acceptEdits
```

`--out` steht **vor** dem Unterbefehl. Weitere Optionen: `--model`, `--timeout` (Default 900 s), `--round`.

Die Laufdaten liegen dauerhaft unter `~/.local/share/izg-bench` (`--out` oder `IZG_BENCH_OUT` aendern das). Nicht in `/tmp` ablegen — die Messung von vor drei Monaten ist der Bezugspunkt der naechsten.

Der erste `run` legt aus den Optionen einen **Messplan** an (`<out>/plans/<task>.json`) und schreibt die Umschaltung jeder Variante hinein. Jeder spaetere `run` derselben Testaufgabe zieht ihn heran; angegebene Optionen schlagen den Plan, weichen sie ab, wird das gemeldet. Damit reicht spaeter:

```bash
python3 scripts/bench.py run --task ticket-anlegen --variant v3 --repeat 3
```

Plan von Hand anlegen oder ansehen: `plan save`, `plan show --task ...`, `plan list`.

Das Skript startet `claude -p` headless mit fester Session-ID, liest danach das Transcript und verbucht pro Lauf eine JSON-Datei. Erfasst werden: exakte `usage`-Werte, `total_cost_usd` und `num_turns` aus der CLI, Cache-Quote, Tool-Aufrufe, Tool-Result-Kontextlast, Subagent-Output, Laufzeit.

**3 Laeufe pro Variante, wo es auf die Zahl ankommt.** Darunter urteilt `compare` trotzdem, kennzeichnet das Urteil aber als *ungesichert*: bei einem Lauf ist die Spanne ein Punkt, Spannen koennen dann nicht ueberlappen — das Ueberlappungskriterium greift ins Leere und jeder Streuungsunterschied wird zum Urteil. Fuer die schnelle Frage "ueberhaupt in die richtige Richtung?" reicht `--repeat 1`; fuer eine Zahl, die jemanden ueberzeugen soll, nicht. Ein Lauf wird nicht verbucht — und darf auch nicht nachgetragen werden — bei:

- Timeout (`--timeout`, Default 900 s)
- fehlendem Transcript (Session-Datei nicht gefunden)
- Fehler-Exitcode (`claude -p` beendet != 0)
- abgebrochenem Lauf (CLI-`subtype` != `success`, z. B. `error_max_turns`, `error_during_execution`)

Ein verworfener Lauf belegt keine Laufnummer: `run` wird erst beim Schreiben der JSON-Datei verbraucht, der naechste Versuch bekommt dieselbe Nummer erneut.

Wurde ein Lauf von Hand ausgefuehrt statt ueber `run`, laesst er sich nachtraeglich verbuchen:

```bash
python3 scripts/bench.py --out /tmp/izg-bench measure \
  --task ticket-anlegen --variant manuell --session-id <uuid>
```

### 4. Ertrag bewerten

Kosten ohne Ertrag sind wertlos: eine Variante, die 60 % spart und die Aufgabe nicht loest, hat verloren. Jeden Lauf ansehen — Ergebnisdateien, Diff, Antworttext — und bewerten:

```bash
python3 scripts/bench.py --out /tmp/izg-bench judge \
  --task ticket-anlegen --variant mit-skill --run 2 --outcome partial --note "Ticket ohne Verlaufseintrag"
```

`ok` nur bei vollstaendiger Loesung. Solange ein Lauf `unset` ist, meldet `compare` fuer die Variante "Ertrag offen" statt eines Urteils. Selbst bewerten ist erlaubt, aber die Kriterien vorher festhalten — nicht nachtraeglich passend machen.

### 5. Vergleichen

```bash
python3 scripts/bench.py --out /tmp/izg-bench compare --baseline ohne-skill
```

Das Urteil ist bewusst zurueckhaltend:

- **Spannen ueberlappen** → "kein belastbarer Unterschied". Nicht wegdiskutieren, nicht auf Mediane ausweichen. Wer trotzdem ein Urteil will, misst mehr Laeufe.
- **n < 3** → Urteil mit dem Zusatz „ungesichert". Als Richtungsanzeige brauchbar, als Beleg nicht.
- **Ertrag offen oder `fail` dabei** → kein Urteil.
- **Testaufgabe, Modell oder Messrunde weichen ab** → kein Urteil, sondern die Aufforderung, neu zu messen. Diese drei verschieben die Kosten, ohne dass die Variante sich geaendert hat.

Nur wenn die Spannen sauber getrennt sind, steht dort ein Prozentwert.

Die Basis wandert beim ersten `--baseline` in den Messplan; spaetere `compare`- und `history`-Aufrufe ziehen sie von dort. Ist keine hinterlegt und wird keine angegeben, vergleicht das Skript gegen die alphabetisch erste Variante und sagt das dazu — dann festlegen statt weiterlesen, sonst bezieht sich das Urteil auf eine Frage, die niemand gestellt hat.

Auf eine Runde einschraenken mit `--round`. `--across-rounds` erzwingt ein Urteil ueber Runden hinweg — als Orientierung brauchbar, als Beleg nicht.

### 6. Ergebnis darstellen

Bei zwei Varianten und klarem Ergebnis genuegt die Markdown-Tabelle aus `compare` plus zwei Saetzen. Bei mehr Varianten, mehreren Tasks oder einem Ergebnis, das jemand ueberzeugen muss: HTML-Report nach [REPORT.md](REPORT.md).

Der Bericht endet mit einem **Urteil**, nicht mit Massnahmen:

- *"`mit-skill` ist um 34 % guenstiger bei gleichem Ertrag (n=5, Spannen getrennt)."*
- *"Kein belastbarer Unterschied. Die Entscheidung faellt nicht ueber Tokens."*

Erst wenn der User danach fragt, weitergehen — zu `izg-improve-token-usage` fuer die Ursachen der teuren Variante, oder zu `izg-create-fixplan` fuer die Umsetzung.

## Optimierung ueber die Zeit belegen

Der haeufigere Fall ist nicht "A oder B?", sondern: *ein Skill wird ueber Monate mehrfach ueberarbeitet — hat das etwas gebracht?* Dafuer gilt eine einzige Regel:

> **Alte Zahlen nie wiederverwenden. Die produktive Fassung in jeder Runde neu mitmessen.**

Zwischen zwei Runden liegt mehr als die Optimierung: ein anderes Modell, ein neuer Systemprompt, eine neue CLI-Version. Wer die neue Fassung gegen die gespeicherten Zahlen der alten stellt, misst zu einem unbekannten Anteil den Versionswechsel von Claude Code und schreibt ihn seiner eigenen Arbeit gut. Das Skript laesst das nicht zu: Laeufe aus zwei Runden oder von zwei Modellen ergeben kein Urteil.

Eine Optimierungsrunde besteht deshalb aus **zwei** Messungen:

```bash
# 1. Die aktuell produktive Fassung erneut messen - die Basis dieser Runde
python3 scripts/bench.py run --task ticket-anlegen --variant v2 --repeat 3

# 2. Die ueberarbeitete Fassung
python3 scripts/bench.py run --task ticket-anlegen --variant v3 --repeat 3 \
  --setup "cp varianten/v3/SKILL.md .claude/skills/foo/SKILL.md"

# 3. Urteil - beide aus derselben Runde
python3 scripts/bench.py compare --task ticket-anlegen --baseline v2
```

Kostet den doppelten Messaufwand. Das ist der Preis dafuer, dass am Ende eine Zahl steht, die traegt.

### Verlauf ansehen

```bash
python3 scripts/bench.py history --task ticket-anlegen
```

Zeigt jede Messrunde mit ihren Varianten und dem rundeninternen Urteil, darunter den Verlauf einer Variante ueber die Runden — mit Markierung, wo Modell oder CLI-Version gewechselt haben.

Der Verlaufsteil ist **Beobachtung mit Datum, kein Beleg**. Er beantwortet "wohin bewegt sich das Niveau", nicht "was hat meine Optimierung gebracht". Die zweite Frage beantwortet nur das Urteil innerhalb einer Runde. Wandert die produktive Fassung dort ohne Zutun nach oben, ist das ein Befund fuer sich — das Niveau ist gestiegen, nicht die Arbeit schlechter geworden.

### Viele Skills nebeneinander

Eine Testaufgabe pro Skill, als Task-Kennung der Skillname. Der Messplan haelt jede Messung fuer sich; `plan list` zeigt, was gemessen ist und wann zuletzt. Nicht alles messen, was sich messen laesst — nur was optimiert werden soll und wo der Messaufwand kleiner ist als die erwartete Ersparnis.

## Grenzen

- **Streuung ist gross.** Modellantworten schwanken zwischen identischen Laeufen erheblich. Deshalb Median und Spanne statt Mittelwert, deshalb das Ueberlappungskriterium — und deshalb traegt ein Urteil aus weniger als 3 Laeufen den Zusatz „ungesichert": es kann die Streuung nicht von der Wirkung trennen.
- **`--setup` wird nicht geprueft.** Laeuft das Kommando ins Leere, misst man klaglos die falsche Variante. Nach dem ersten Lauf einer Variante stichprobenartig nachsehen, ob der Zustand stimmt.
- **Tool-Result-Tokens sind geschaetzt** (~4 Zeichen pro Token). Die `usage`-Werte und `total_cost_usd` sind exakt — Urteile nur auf diesen faellen.
- **Nur Claude Code.** Vibe, Codex und Gemini schreiben kein kompatibles Transcript. Deren Varianten lassen sich hier nicht gegeneinander stellen.
- **Der Preis eines Laufs haengt am Modell.** Varianten immer mit demselben `--model` messen. Ohne `--model` entscheidet die CLI — und kann zwischen zwei Runden anders entscheiden.
- **Vergleich ueber Zeit nur mit neu gemessener Basis.** Modellwechsel, geaenderte Systemprompts und neue CLI-Versionen verschieben das Niveau. Alte Laufdaten belegen, was damals war; ein Urteil ueber eine Optimierung tragen sie nicht. Siehe "Optimierung ueber die Zeit belegen".
- **Die Messrunde ist eine Behauptung.** Sie kommt aus dem Datum, nicht aus einer Pruefung der Umgebung. Wer zwei Messungen mit Wochen Abstand von Hand auf dieselbe `--round` setzt, hebelt genau die Sperre aus, die ihn schuetzen soll.
