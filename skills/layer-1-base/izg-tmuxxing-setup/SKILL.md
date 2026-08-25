---
name: izg-tmuxxing-setup
description: Einmaliger Maschinen-Setup fuer izg-tmuxxing - tmux/kitty-Configs deployen, fzf installieren und den Ticket-Picker-Popup per Keybinding einrichten. Laeuft EINMAL PRO MASCHINE, NICHT zur Laufzeit eines Workers. Use when eine neue Maschine fuer izg-tmuxxing eingerichtet wird, tmux.conf/kitty.conf fehlen, oder der Ticket-Picker (bind t) noch nicht konfiguriert ist. NICHT verwenden, um einen Worker zu starten oder zu steuern - dafuer izg-tmuxxing selbst.
---

## Zweck

Dieser Skill deckt den Teil von `izg-tmuxxing` ab, der **einmal pro Maschine** laeuft
und danach nicht mehr angefasst wird: Configs deployen, Abhaengigkeiten installieren,
Keybindings einrichten. Bewusst als eigener Skill statt als `references/`-Abschnitt in
`izg-tmuxxing`, damit beim normalen Worker-Starten kein Setup-Pfad mehr im Kontext
liegt, an dem sich ein schwaches Modell verlaufen kann.

Laufzeit-Nutzung (Worker starten, fuettern, beobachten, beenden) bleibt in
`izg-tmuxxing` — dorthin wechseln, sobald die Maschine eingerichtet ist.

## Configs

`configs/tmux.conf`, `configs/kitty.conf`, `configs/current-theme.conf` liegen in
diesem Skill-Ordner und werden auf der Zielmaschine an die jeweils erwarteten Pfade
verlinkt bzw. kopiert (z.B. `~/.tmux.conf`, `~/.config/kitty/kitty.conf`).

## Ticket-Picker (Popup)

Ein Pattern, um einem bereits laufenden Worker-Pane direkt ein offenes Ticket
zuzuweisen — per tmux-Popup, ohne die Tastatur zu verlassen.

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
