# tmuxxing Cheatsheet

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
