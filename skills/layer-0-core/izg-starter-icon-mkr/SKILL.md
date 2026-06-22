---
name: izg-starter-icon-mkr
description: "Erstellt für eine selbstgebaute Server-App (Flask, FastAPI, Streamlit, Node etc.) ein Desktop-Startericon auf dem Schreibtisch. Beim Klick werden laufende Instanzen beendet, der Server losgelöst gestartet und der Browser geöffnet, ohne dass ein Terminalfenster hängen bleibt. Dieser Skill sollte verwendet werden, wenn ein Doppelklick-Starter, Desktop-Icon oder Launcher für eine lokale App gewünscht ist (mach mir ein Startericon, Desktop-Verknüpfung, App per Klick starten). Prüft dabei verpflichtend, dass die App einen Beenden-Button hat und kein Terminalfenster offen bleibt."
layer: 1
dependencies: []
---

# IZG Starter Icon Maker

Globaler Skill zum Erzeugen von Schreibtisch-Startericons für die lokal gebauten
Server-Apps. Linux Mint / Cinnamon, Desktop-Ordner `~/Schreibtisch`.

## Was der Skill liefert

Pro App entsteht:

1. Ein Launcher-Wrapper `~/.local/bin/<slug>-launcher.sh`, der beim Klick:
   - laufende Instanzen beendet (über TCP-Port und/oder Prozess-Pattern),
   - den Server losgelöst startet (`setsid`/`disown`, Logs in Datei),
   - auf den Port wartet und den Browser auf die URL öffnet,
   - ein eventuell sichtbares Terminalfenster automatisch schließt.
2. Ein `<Name>.desktop` auf `~/Schreibtisch` (ausführbar + als trusted markiert)
   und eine Kopie im Anwendungsmenü (`~/.local/share/applications/`).

## Ablauf

### Schritt 1 — App-Parameter ermitteln
Aus dem Projekt Startbefehl, Arbeitsverzeichnis, Port und URL bestimmen. Details
und typische Startbefehle pro Framework in `references/app_check.md` (Abschnitt
1). Im Zweifel den Nutzer nur nach dem Startbefehl und Port fragen, den Rest
ableiten.

### Schritt 2 — Pflicht-Check A: Beenden-Button
Prüfen, ob die App den **Server** sauber beenden kann (nicht nur den Browser-Tab
schließt). Fehlt das, den passenden Shutdown-Endpoint plus Button ergänzen —
Code-Vorlagen je Framework in `references/app_check.md` (Abschnitt 2). Diesen
Check immer durchführen, auch wenn nur das Icon angefragt wurde; kurz melden, was
gefunden bzw. ergänzt wurde.

### Schritt 3 — Pflicht-Check B: Kein hängendes Terminal
Standardmäßig wird das `.desktop` mit `Terminal=false` erzeugt, der Server läuft
losgelöst — es öffnet sich kein Terminal. Prüfen, ob ein bestehendes Start-Skript
selbst ein Terminal aufmacht (`gnome-terminal -- ...`); falls ja, im Startbefehl
entfernen und nur den reinen Server-Befehl übergeben. Siehe `app_check.md`
(Abschnitt 3). `--show-terminal` nur nutzen, wenn Logs sichtbar sein müssen — dann
schließt der Launcher das Terminal nach dem Start selbst.

### Schritt 4 — Icon erzeugen
`scripts/make_starter_icon.py` ausführen:

```bash
python3 scripts/make_starter_icon.py \
  --name "Stonky" \
  --workdir "/home/izg/Dokumente/AI/Stonky" \
  --start "streamlit run app.py --server.port 8501 --server.headless true" \
  --port 8501 \
  --match "app.py"
```

`--url` wird auf `http://localhost:<port>` gesetzt, wenn nicht angegeben.
`--match` defaultet auf den Startbefehl.

**Custom-Icon (Default):** Ohne `--icon` wird automatisch ein Icon im
IZG-Designstil erzeugt — dunkle abgerundete Kachel mit Canto-Green-Glyph
(`#06fc99`), passend zu den bestehenden Desktop-Icons. Gespeichert unter
`~/.local/share/icons/<slug>.svg`. Glyph-Variante über `--glyph` wählen:
`letter` (Initialen, Default), `play` (Starter-Dreieck), `terminal`
(Dashboard-Fenster), `rhombus` (Raute). Ein eigenes Icon stattdessen via
`--icon /pfad/zum/bild.svg`, ein Theme-Icon via `--icon network-server`.

Das Icon kann auch separat erzeugt/angepasst werden mit
`scripts/make_icon.py --name "..." --glyph play --out ~/.local/share/icons/x.svg`.
Für komplexere, app-spezifische Motive das SVG danach von Hand verfeinern (die
bestehenden Icons wie `claude-config-dashboard.svg` sind handgezeichnete SVGs im
selben Stil — als Vorlage nutzbar).

### Schritt 5 — Verifizieren
`bash -n` auf den Launcher und (falls vorhanden) `desktop-file-validate` auf die
`.desktop`-Datei laufen lassen. Siehe `app_check.md` (Abschnitt 4). Dem Nutzer
melden, wo Icon, Launcher und Log liegen.

## Wichtige Hinweise

- Der Launcher beendet alte Instanzen über Port **und** Pattern — beides angeben,
  wenn die App auf festem Port läuft, sonst reicht das Pattern.
- Logs landen in `~/.local/share/izg-starter/logs/<slug>.log` — erster Anlaufpunkt
  bei Startproblemen.
- Cinnamon zeigt ein frisches `.desktop` evtl. erst als Textdatei; das Skript
  setzt `metadata::trusted=true`. Falls das Icon nicht startet: Rechtsklick →
  "Starten erlauben".
