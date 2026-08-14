---
name: izg-benchmark-actions
description: Vergleicht die Kosten mehrerer Varianten eines Ablaufs — mit oder ohne Skill, alte gegen neue Fassung, Subagent gegen Direktarbeit — durch wiederholte, isolierte Messlaeufe auf derselben Testaufgabe und faellt ein belegtes Urteil.
layer: 3
dependencies: []
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

Als Datei ablegen und mit `--prompt-file` verwenden. Nie pro Variante umformulieren; eine geaenderte Testaufgabe macht den Vergleich wertlos.

### 2. Varianten und Umschaltung festlegen

Fuer jede Variante muss klar sein, wie der Zustand hergestellt wird. Das gehoert in `--setup` (Shell-Kommando, laeuft vor jedem Lauf im Projektverzeichnis):

```bash
--setup "cp variants/mit-skill/SKILL.md .claude/skills/foo/SKILL.md"
--setup "git checkout v2 -- .claude/"
```

Ohne `--setup` misst man dreimal denselben Zustand. Nach dem letzten Lauf den Ausgangszustand wiederherstellen.

**Isolation statt Segmentierung:** Jeder Lauf bekommt eine eigene Session-ID und damit ein eigenes Transcript. Nichts wird nachtraeglich aus einer laufenden Session herausgerechnet.

### 3. Laeufe ausfuehren

Jeder Lauf kostet echtes Geld. **Vor dem ersten `run` dem User die Rechnung nennen** — Anzahl Varianten x `--repeat` — und bestaetigen lassen.

```bash
python3 scripts/bench.py --out /tmp/izg-bench run \
  --task ticket-anlegen --variant ohne-skill \
  --prompt-file aufgabe.md --repeat 3 \
  --project /pfad/zum/projekt --setup "..." --permission-mode acceptEdits
```

`--out` steht **vor** dem Unterbefehl. Weitere Optionen: `--model`, `--timeout` (Default 900 s).

Das Skript startet `claude -p` headless mit fester Session-ID, liest danach das Transcript und verbucht pro Lauf eine JSON-Datei. Erfasst werden: exakte `usage`-Werte, `total_cost_usd` und `num_turns` aus der CLI, Cache-Quote, Tool-Aufrufe, Tool-Result-Kontextlast, Subagent-Output, Laufzeit.

**Mindestens 3 Laeufe pro Variante.** Darunter verweigert `compare` das Urteil. Ein Lauf, der in einen Timeout oder Fehler laeuft, wird nicht verbucht — er darf auch nicht nachgetragen werden.

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
- **n < 3** → kein Urteil.
- **Ertrag offen oder `fail` dabei** → kein Urteil.

Nur wenn die Spannen sauber getrennt sind, steht dort ein Prozentwert.

### 6. Ergebnis darstellen

Bei zwei Varianten und klarem Ergebnis genuegt die Markdown-Tabelle aus `compare` plus zwei Saetzen. Bei mehr Varianten, mehreren Tasks oder einem Ergebnis, das jemand ueberzeugen muss: HTML-Report nach [REPORT.md](REPORT.md).

Der Bericht endet mit einem **Urteil**, nicht mit Massnahmen:

- *"`mit-skill` ist um 34 % guenstiger bei gleichem Ertrag (n=5, Spannen getrennt)."*
- *"Kein belastbarer Unterschied. Die Entscheidung faellt nicht ueber Tokens."*

Erst wenn der User danach fragt, weitergehen — zu `izg-improve-token-usage` fuer die Ursachen der teuren Variante, oder zu `izg-create-fixplan` fuer die Umsetzung.

## Grenzen

- **Streuung ist gross.** Modellantworten schwanken zwischen identischen Laeufen erheblich. Deshalb Median und Spanne statt Mittelwert, deshalb n >= 3, deshalb das Ueberlappungskriterium.
- **`--setup` wird nicht geprueft.** Laeuft das Kommando ins Leere, misst man klaglos die falsche Variante. Nach dem ersten Lauf einer Variante stichprobenartig nachsehen, ob der Zustand stimmt.
- **Tool-Result-Tokens sind geschaetzt** (~4 Zeichen pro Token). Die `usage`-Werte und `total_cost_usd` sind exakt — Urteile nur auf diesen faellen.
- **Nur Claude Code.** Vibe, Codex und Gemini schreiben kein kompatibles Transcript. Deren Varianten lassen sich hier nicht gegeneinander stellen.
- **Der Preis eines Laufs haengt am Modell.** Varianten immer mit demselben `--model` messen.
- **Kein Vergleich ueber Zeit.** Modellwechsel, geaenderte Systemprompts und neue CLI-Versionen verschieben das Niveau. Alte Laufdaten nicht gegen neue stellen.
