---
name: izg-tmuxxing
description: Eigenstaendige CLI-Agenten (Vibe, Claude) als Worker in tmux-Panes starten, mit Aufgaben fuettern, beobachten und beenden - statt Subagents im eigenen Chat zu spawnen. Use when Arbeit an einen zweiten Agenten delegiert werden soll, mehrere Aufgaben parallel laufen, der Nutzer zusehen oder uebernehmen will, oder Token gespart werden sollen.
layer: 1
dependencies: []
---

# izg-tmuxxing

Ein Orchestrator (du) startet Worker-Agenten in tmux-Panes. Der Worker ist ein
eigener Prozess mit eigenem Kontextfenster: **du bezahlst nur Auftrag und Ergebnis,
nicht seine Arbeit**.

## Ablauf

```bash
T=<skill-pfad>/scripts/tmuxx.sh

bash $T start recherche /pfad/zum/projekt --worker claude --model sonnet --split
bash $T send  recherche "Auftrag in einem Absatz, mit Pfaden und erwartetem Output-Format."
bash $T await recherche 120       # blockiert bis idle|dialog|dead, gibt das Ergebnis aus
bash $T answer recherche 2        # blockierende Auswahl beantworten (default 2)
bash $T status recherche          # idle | busy | dialog | dead, ohne zu warten
bash $T peek   recherche 15       # gefilterte Pane-Zeilen, nur zur Fehlersuche
bash $T cost   recherche          # Tokenverbrauch des Workers
bash $T stop   recherche
```

| Pane-Ziel | Wirkung |
|---|---|
| `--pane %3` | uebernimmt ein offenes, leeres Pane, gibt es bei `stop` zurueck |
| `--split` | neues Pane neben dir (nur innerhalb von tmux) |
| keins | detached in eigener Session |

| Worker | Wann |
|---|---|
| `--worker vibe` | Standard fuer Routinearbeit |
| `--worker claude --model sonnet` | wenn Claude-Skills/Hooks gebraucht werden |
| `--worker "<beliebiges kommando>"` | alles andere |

**Regeln:**
1. Der Worker startet **kalt** — tmux transportiert keinen Kontext. Er kennt nur
   Workdir und deinen Auftragstext. Absolute Pfade, Output-Format, Abbruchbedingung.
2. `send && await` in **einem** Bash-Aufruf, nie ueber Turns pollen.
3. Ergebnis aus Dateien verifizieren, nicht der Erfolgsmeldung glauben.
4. `stop` am Ende.

Ein zweites, unabhaengiges Pattern fuer denselben Skill-Bereich (Ticket direkt per
Popup einem laufenden Pane zuweisen statt per `tmuxx.sh` zu starten) inklusive
einmaligem Maschinen-Setup steht in `izg-tmuxxing-setup`.

## Zustand

Pro Worker eine Datei `~/.tmuxx/<name>.state` (`pane_id`, tmux-Session, Workdir,
Worker-Typ, Claude-`sessionId`, Startzeit). `stop` raeumt sie weg. Bei Claude-Workern
kommt der Status aus `claude agents --json` (Name = Worker-Name), nicht aus
Pane-Scraping — deshalb ist `--model` auch nur dort gueltig.

Volle Faktensammlung inkl. Messprotokollen: `testing/tmuxxxing.md` im ai-SKILL-set-Repo.

## Weiterfuehrend

- Willst du wissen, warum das Script bestimmte Dinge tut (Pane-IDs statt Indizes,
  Busy-Erkennung, Quoting) statt es einfach zu benutzen: `references/rationale.md`.
- Bespielst du mehrere Panes gleichzeitig mit verteilten Tickets (Dateikonflikte,
  Orchestrierungs-Playbook): `references/orchestration.md`.
