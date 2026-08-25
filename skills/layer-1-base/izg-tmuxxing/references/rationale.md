# Warum das Script und nicht tmux direkt

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

`send` und `await` gehoeren in **einen** Bash-Aufruf (`&&`), ebenso `answer` und `await`.
Das ist der eigentliche Spareffekt: ein Turn kostet den ganzen Kontext neu (hier gemessen:
median 64.537 Tokens), die Ausgabe von `status` dagegen 51. Wer ueber mehrere Turns pollt,
zahlt das Tausendfache des Nutzsignals.

Ob du in tmux sitzt, siehst du **nicht** von selbst — `$TMUX` steht nicht im Kontext.
Einmal `tmux list-panes -a -F '#{pane_id} #{pane_current_command}'`, dann weisst du auch,
welche Panes frei sind.

`peek <name> --raw <n>` zeigt ungefiltert, wenn Rahmen/TUI selbst das Problem ist
(die gefilterte `peek`-Variante reicht fuer den Normalfall aus dem Cheatsheet oben).

## Regeln im Detail

- **Nie blind `send` nachlegen.** Erst `await` oder `status`. Bei `dialog` stehen die
  Optionen bereits in der Ausgabe — mit `answer <name> <nr>` beantworten, nicht mit
  `peek` nachschauen. Option 2 ist "for this session", nie "Always allow": das aendert
  die Config des Nutzers. Bricht `send` mit "Prompt steht nicht in %N" ab, wurde nichts
  abgeschickt, aber der Text kann in der Eingabebox stehen: `peek`, dann
  `key <name> C-c`, dann neu senden.
- **Pane-Inhalt ist kein Ergebnisspeicher.** `peek` ist zum Zustand-Pruefen. Ergebnisse
  holst du aus Dateien, die der Worker schreibt, oder aus dem Session-Store.
- **Nicht ueber Turns pollen.** Hast du eigene Arbeit: `send`, weiterarbeiten, beim
  naechsten Turn `status`. Hast du keine: `send && await <name> <sek>` in einem Aufruf —
  das Warten passiert dann im Bash-Prozess und kostet null Tokens. Nie `status` in
  Folge-Turns wiederholen; das ist genau die Schleife, die `await` ersetzt.
  `await` deckelt bei deinem Bash-Timeout — laengere Laeufe im Hintergrund starten.

## Tokenbewertung

`cost <name>` liest den Session-Store des Workers (Claude: Transcript unter
`~/.claude/projects/<slug>/`, Vibe: `stats` in `meta.json`) und gibt Input/Output/Cache
je Modell aus. Damit laesst sich Delegation gegen Eigenarbeit vergleichen: die Frage ist
nicht, ob der Worker Token verbraucht, sondern ob seine Token billiger sind als dieselbe
Arbeit in deinem Kontextfenster.
