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
bash $T await recherche 120       # blockiert bis idle|dialog|dead, gibt das Ergebnis aus
bash $T answer recherche 2        # blockierende Auswahl beantworten (default 2)
bash $T status recherche          # idle | busy | dialog | dead, ohne zu warten
bash $T peek   recherche 15       # gefilterte Pane-Zeilen, nur zur Fehlersuche
bash $T peek   recherche --raw 40 # ungefiltert, wenn Rahmen/TUI selbst das Problem ist
bash $T cost   recherche          # Tokenverbrauch des Workers
bash $T stop   recherche
```

`send` und `await` gehoeren in **einen** Bash-Aufruf (`&&`), ebenso `answer` und `await`.
Das ist der eigentliche Spareffekt: ein Turn kostet den ganzen Kontext neu (hier gemessen:
median 64.537 Tokens), die Ausgabe von `status` dagegen 51. Wer ueber mehrere Turns pollt,
zahlt das Tausendfache des Nutzsignals.

Wohin der Worker kommt:

| Option | Wirkung |
|---|---|
| `--pane %3` | uebernimmt ein offenes, leeres Pane des Nutzers und gibt es bei `stop` als Shell zurueck |
| `--split` | neues Pane neben dir (nur innerhalb von tmux) |
| keins | detached in eigener Session (`tmux attach -t tmuxx-<name>`) |

Ob du in tmux sitzt, siehst du **nicht** von selbst — `$TMUX` steht nicht im Kontext.
Einmal `tmux list-panes -a -F '#{pane_id} #{pane_current_command}'`, dann weisst du auch,
welche Panes frei sind.

Worker-Wahl:

| Worker | Wann | Kosten |
|---|---|---|
| `--worker vibe` | Standard fuer Routinearbeit | Subscription |
| `--worker claude --model sonnet` | wenn Claude-Skills/Hooks gebraucht werden | Token, aber deutlich billiger als eigener Kontext |
| `--worker "<beliebiges kommando>"` | alles andere | — |

## Regeln

1. **Auftrag vollstaendig formulieren.** Absolute Pfade, erwartetes Output-Format,
   Abbruchbedingung. Der Worker kennt euer Gespraech nicht. Vage Auftraege gehen schief.
2. **Nie blind `send` nachlegen.** Erst `await` oder `status`. Bei `dialog` stehen die
   Optionen bereits in der Ausgabe — mit `answer <name> <nr>` beantworten, nicht mit
   `peek` nachschauen. Option 2 ist "for this session", nie "Always allow": das aendert
   die Config des Nutzers. Bricht `send` mit "Prompt steht nicht in %N" ab, wurde nichts
   abgeschickt, aber der Text kann in der Eingabebox stehen: `peek`, dann
   `key <name> C-c`, dann neu senden.
3. **Ergebnis verifizieren, nicht der Erfolgsmeldung glauben.** Ein sandboxter Worker
   meldet `FERTIG` und hat nach `/tmp` geschrieben. Nach jedem Lauf Zieldatei pruefen.
4. **Pane-Inhalt ist kein Ergebnisspeicher.** `peek` ist zum Zustand-Pruefen. Ergebnisse
   holst du aus Dateien, die der Worker schreibt, oder aus dem Session-Store.
5. **Nicht ueber Turns pollen.** Hast du eigene Arbeit: `send`, weiterarbeiten, beim
   naechsten Turn `status`. Hast du keine: `send && await <name> <sek>` in einem Aufruf —
   das Warten passiert dann im Bash-Prozess und kostet null Tokens. Nie `status` in
   Folge-Turns wiederholen; das ist genau die Schleife, die `await` ersetzt.
   `await` deckelt bei deinem Bash-Timeout — laengere Laeufe im Hintergrund starten.
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
- **Busy erkennen ist zweistufig** — die Claude-Registry flippt nach `send` erst mit
  Verzoegerung auf `busy`; wer ihr allein glaubt, meldet in der Luecke faelschlich `idle`
  und verwirft ein Ergebnis. Die Spinnerzeile allein geht auch nicht: Claude laesst
  `✻ Brewed for 4s` nach dem Lauf im Transcript stehen, das Pane sieht ewig busy aus.
  Massgeblich ist Registry **oder** `esc to interrupt`, plus drei bestaetigte `idle`-Proben.

## Tokenbewertung

`cost <name>` liest den Session-Store des Workers (Claude: Transcript unter
`~/.claude/projects/<slug>/`, Vibe: `stats` in `meta.json`) und gibt Input/Output/Cache
je Modell aus. Damit laesst sich Delegation gegen Eigenarbeit vergleichen: die Frage ist
nicht, ob der Worker Token verbraucht, sondern ob seine Token billiger sind als dieselbe
Arbeit in deinem Kontextfenster.

## Ticket-Picker (Popup)

Ein zweites, unabhaengiges Pattern fuer denselben Skill-Bereich: statt einen Worker
per `tmuxx.sh` zu starten, weist du ein **offenes Ticket direkt einem bereits
laufenden Pane zu** — per tmux-Popup, ohne die Tastatur zu verlassen.

Bausteine:

1. `scripts/ticket_board.sh <projekt-pfad>` — listet OPEN/IN-PROGRESS/BLOCKED aus
   `tickets/`. Passiv, gedacht fuer `watch -n 5 ...` in einer schmalen Statuszeile.
2. `scripts/ticket_picker.sh <projekt-pfad>` — interaktiv: baut aus `tickets/open/*.md`
   eine `fzf`-Liste (`id`, `title`), schickt bei Auswahl
   `arbeite an <ID>: <Titel>` per `tmux send-keys -l` an `$TARGET_PANE` (Env-Var,
   muss vom Aufrufer gesetzt sein — die pane_id des Panes, aus dem heraus
   ausgewaehlt wurde).
3. tmux-Keybinding, das `TARGET_PANE` **vor** dem Popup einfaengt (sonst zeigt
   `#{pane_id}` auf das Popup-Pane selbst statt auf den Ziel-Worker):

```tmux
bind t run-shell "tmux display-popup -E -w 80% -h 60% -T Tickets \
  \"TARGET_PANE=#{pane_id} bash '<repo>/scripts/ticket_picker.sh' '<projekt-pfad>'\""
```

Voraussetzung: `fzf` installiert (`sudo apt install fzf`). Ohne echtes Terminal
(z.B. Testlauf ohne tty) bricht `fzf` mit "inappropriate ioctl for device" ab —
das ist erwartetes Verhalten ausserhalb eines echten Popups, kein Bug.

Aktuell sind `ticket_board.sh`/`ticket_picker.sh` generisch (nehmen jeden
Projektpfad mit `tickets/`-Ordner entgegen), liegen aber im Top-Level
`ai-SKILL-set/scripts/`, nicht im Skill-Ordner selbst — wer sie in ein fremdes
Projekt pullen will, kopiert sie manuell mit, `pull_skill.py` fasst sie nicht an.
Das Keybinding-Beispiel oben ist bewusst mit Platzhaltern (`<repo>`,
`<projekt-pfad>`) statt fester Pfade notiert.

### Parallelarbeit: Dateikonflikte und Commits (IZG-T-198)

Alle Panes teilen sich denselben Working-Tree derselben Checkout — der Kernkonflikt
bei mehreren gleichzeitig verteilten Tickets ist gleichzeitiges Schreiben derselben
Datei, kein Git-Merge-Problem. Gewaehlte Absicherung: **disjunkte Dateibereiche pro
Verteilrunde** (Tickets, die dieselben Dateien/Ordner betreffen, nicht im selben
Durchgang an unterschiedliche Panes verteilen), zusammen mit der bestehenden
Konvention, beim Commit gezielt einzelne Dateien zu stagen (`git add <datei>`, nie
`-A`/`.`) statt versehentlich fremde Aenderungen mit einzuchecken.

Verworfen: `git worktree` pro Pane (verlangt einen eigenen Branch je Worktree,
widerspricht der No-Branch-Konvention direkt auf main); ein reiner Commit-Lock
(loest nur die Symptom-Ebene, nicht das gleichzeitige Ueberschreiben derselben
Datei vor dem Commit).

Der Picker selbst warnt nicht bei ueberlappenden Dateibereichen und wird es auch
nicht tun — er verteilt seit IZG-T-195 gar nicht mehr selbst. Die Pruefung liegt
beim orchestrierenden Agenten, siehe Schritt 2 des Playbooks unten.

### Orchestrierungs-Playbook fuer verteilte Tickets (IZG-T-196)

Der Picker (IZG-T-195) uebergibt dem orchestrierenden Agenten nur die Ticket-Auswahl.
Alles Weitere — Ziel-Panes finden, Auftraege verschicken, nachlegen, pruefen — macht
der Agent selbst. Ablauf, Schritt fuer Schritt:

1. **Ziel-Panes ermitteln:** `ListAgents` aufrufen. Liefert je Peer-Session
   `busy`/`idle` und die tmux-Pane-Zuordnung. Kein `tmux list-panes`-Raten, kein
   Scrapen von `capture-pane` — Scraping ist unzuverlaessig: ein Vollbild-Kommando
   im Pane kann den Busy-Indikator verdecken, ein Watcher meldet dann faelschlich
   "fertig", obwohl der Agent noch arbeitet. Nur Sessions mit Status `idle` sind
   Kandidaten fuer einen Auftrag.
2. **Dateibereiche pruefen:** Fuer jedes gewaehlte Ticket den betroffenen
   Dateibereich bestimmen (Ticketbeschreibung / Titel). Zwei Tickets mit
   ueberlappendem Bereich NICHT im selben Durchgang an unterschiedliche Panes
   verteilen (Regel aus IZG-T-198). Diese Pruefung ist Handarbeit des Agenten und
   bleibt es — es gibt keine geplante Automatisierung dafuer.
   Ueberlappung sichtbar melden, nicht still serialisieren oder eines der beiden
   Tickets stillschweigend zurueckhalten.
3. **Vor dem Versand Status wechseln:** `bash scripts/tickets.sh move <ID>
   in-progress "An Pane %X verteilt" --by <agent>` ausfuehren. Schlaegt der
   Statuswechsel fehl, wird kein Auftrag verschickt. Das ist zugleich die Sperre
   gegen Doppelvergabe: das Ticket liegt danach nicht mehr in `tickets/open/` und
   taucht im Picker nicht mehr auf.
4. **Auftrag verschicken:** Pro Pane genau ein Auftrag pro Durchgang. Der
   Auftragstext nennt die Dateiabgrenzung gegenueber den parallel laufenden Panes
   explizit und schliesst "nicht committen" ein.
5. **Nachlegen ohne Polling:** `SendMessage` mit `notify_when_idle: true` statt
   den Pane-Status abzufragen. Beim Nachlegen: `/clear` im Zielpane, kurze Pause,
   dann der naechste Auftrag.
6. **Ueberhang behandeln:** Mehr gewaehlte Tickets als idle Panes → Ueberhang
   sichtbar melden, nicht verwerfen und nicht blind an ein bereits belegtes Pane
   schicken. Panes koennen legitim leer ausgehen, wenn die Dateibereiche das
   verlangen (Schritt 2).
7. **Ergebnisse pruefen:** Bevor ein Ticket auf `done` geht, das Ergebnis selbst
   verifizieren (Diff lesen, Akzeptanzkriterien pruefen). Der Abschlussbericht des
   Agenten allein ist kein Nachweis.

Nicht Teil dieses Playbooks: Dateikonflikte und Commits als solche — siehe Abschnitt
oben (IZG-T-198).

## Zustand

Pro Worker eine Datei `~/.tmuxx/<name>.state` (`pane_id`, tmux-Session, Workdir,
Worker-Typ, Claude-`sessionId`, Startzeit). `stop` raeumt sie weg. Bei Claude-Workern
kommt der Status aus `claude agents --json` (Name = Worker-Name), nicht aus
Pane-Scraping — deshalb ist `--model` auch nur dort gueltig.

Volle Faktensammlung inkl. Messprotokollen: `testing/tmuxxxing.md` im ai-SKILL-set-Repo.
