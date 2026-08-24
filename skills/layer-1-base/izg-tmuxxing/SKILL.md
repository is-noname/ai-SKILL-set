---
name: izg-tmuxxing
description: Eigenstaendige CLI-Agenten (Vibe, Claude) als Worker in tmux-Panes starten, mit Aufgaben fuettern, beobachten und beenden - statt Subagents im eigenen Chat zu spawnen. Use when Arbeit an einen zweiten Agenten delegiert werden soll, mehrere Aufgaben parallel laufen, der Nutzer zusehen oder uebernehmen will, oder Token gespart werden sollen.
layer: 1
dependencies: []
---

# izg-tmuxxing

Ein Orchestrator (du) startet Worker-Agenten in tmux-Panes. Der Worker ist ein
eigener Prozess mit eigenem Kontextfenster: **du bezahlst nur Auftrag und Ergebnis,
nicht seine Arbeit**. Das ist der Hauptgrund fuer diesen Skill.

tmux transportiert **keinen Kontext**. Ein Worker startet kalt und kennt nur
Workdir (Projektdateien, `CLAUDE.md`/`AGENTS.md`, Skills) plus deine Aufgabe.
Das ist gewollt — schreibe Auftraege entsprechend vollstaendig.

Alle Mechanik steckt in `scripts/tmuxx.sh`. Nutze das Script, nicht rohe
tmux-Kommandos: es kapselt die Fallen, die real Schaden angerichtet haben.

## Ablauf

```bash
T=<skill-pfad>/scripts/tmuxx.sh

bash $T start recherche /pfad/zum/projekt --worker claude --model sonnet --split
bash $T send  recherche "Auftrag in einem Absatz, mit Pfaden und erwartetem Output-Format."
bash $T status recherche          # idle | busy | dialog | dead
bash $T peek   recherche 40       # letzte Pane-Zeilen ansehen
bash $T cost   recherche          # Tokenverbrauch des Workers
bash $T stop   recherche
```

`--split` legt den Worker sichtbar neben dich (nur innerhalb von tmux).
Ohne `--split` laeuft er detached in eigener Session (`tmux attach -t tmuxx-<name>`).

Worker-Wahl:

| Worker | Wann | Kosten |
|---|---|---|
| `--worker vibe` | Standard fuer Routinearbeit | Subscription |
| `--worker claude --model sonnet` | wenn Claude-Skills/Hooks gebraucht werden | Token, aber deutlich billiger als eigener Kontext |
| `--worker "<beliebiges kommando>"` | alles andere | — |

## Regeln

1. **Auftrag vollstaendig formulieren.** Absolute Pfade, erwartetes Output-Format,
   Abbruchbedingung. Der Worker kennt euer Gespraech nicht. Vage Auftraege gehen schief.
2. **Nie blind `send` nachlegen.** Erst `status`. Bei `dialog` mit
   `bash $T key <name> Down Enter` bedienen — bei Permission-Prompts Option 2
   ("remainder of this session"), nie "Always allow": das aendert die Config des Nutzers.
   Bricht `send` mit "Prompt steht nicht in %N" ab, wurde nichts abgeschickt, aber der
   Text kann in der Eingabebox stehen: `peek`, dann `key <name> C-c`, dann neu senden.
3. **Ergebnis verifizieren, nicht der Erfolgsmeldung glauben.** Ein sandboxter Worker
   meldet `FERTIG` und hat nach `/tmp` geschrieben. Nach jedem Lauf Zieldatei pruefen.
4. **Pane-Inhalt ist kein Ergebnisspeicher.** `peek` ist zum Zustand-Pruefen. Ergebnisse
   holst du aus Dateien, die der Worker schreibt, oder aus dem Session-Store.
5. **Nicht pollen.** Nach `send` normal weiterarbeiten und beim naechsten Turn `status`
   fragen. Turns unter ~3 s verschwinden in jeder Poll-Schleife ohnehin.
6. **Aufraeumen.** `stop` am Ende — sonst bleiben Panes und Prozesse stehen.

## Warum das Script und nicht tmux direkt

- **`pane_id` statt `session:window.index`** — Indizes verschieben sich, sobald der
  Nutzer Panes dreht. Real passiert: ein Worker-Prompt landete im Orchestrator-Pane und
  wurde als Nutzernachricht abgeschickt. rc=0, kein Fehler.
- **Prompt einzeilig** — ein `\n` im Buffer schickt bei Vibe vorzeitig ab und die
  zweite Message enthaelt den ersten Teil erneut. `send` normalisiert Zeilenumbrueche.
- **Text und `Enter` getrennt**, dazwischen Verifikation, dass der Text wirklich im
  Ziel-Pane steht — sonst schickt `Enter` nur einen offenen Dialog ab.
- **`-x 200 -y 50`** bei detached Sessions, sonst 80x24 und die TUI bricht um.
- **Quoting** — `send-keys` ohne `-l` frisst Leerzeichen (`echoHallohier`), still.

## Tokenbewertung

`cost <name>` liest den Session-Store des Workers (Claude: Transcript unter
`~/.claude/projects/<slug>/`, Vibe: `stats` in `meta.json`) und gibt Input/Output/Cache
je Modell aus. Damit laesst sich Delegation gegen Eigenarbeit vergleichen: die Frage ist
nicht, ob der Worker Token verbraucht, sondern ob seine Token billiger sind als dieselbe
Arbeit in deinem Kontextfenster.

## Zustand

Pro Worker eine Datei `~/.tmuxx/<name>.state` (`pane_id`, tmux-Session, Workdir,
Worker-Typ, Claude-`sessionId`, Startzeit). `stop` raeumt sie weg. Bei Claude-Workern
kommt der Status aus `claude agents --json` (Name = Worker-Name), nicht aus
Pane-Scraping — deshalb ist `--model` auch nur dort gueltig.

Volle Faktensammlung inkl. Messprotokollen: `testing/tmuxxxing.md` im ai-SKILL-set-Repo.
