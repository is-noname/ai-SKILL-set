# Excalidraw-JSON-Schema für das obsidian-excalidraw-plugin

Getestet in: `Chuck/Excalidraw/CFO-Test-Diagramm.md` (Vault "Chuck", Ordner eine Ebene
über dem CFO-Projekt). Erster Testlauf am 2026-08-28 hat auf Anhieb korrekt gerendert.

## Dateiformat (.md)

```
---

excalidraw-plugin: parsed
tags: [excalidraw]

---
==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress Drawing data with the command palette: 'Decompress current Excalidraw file'. For more info check in plugin settings under 'Saving'


# Excalidraw Data

## Text Elements
<Textinhalt Element 1> ^<id1>

<Textinhalt Element 2> ^<id2>

%%
## Drawing
```json
{ ...vollständiges Excalidraw-JSON... }
```
%%
```

Regeln:
- Frontmatter `excalidraw-plugin: parsed` ist Pflicht, sonst erkennt das Plugin die Datei nicht.
- `## Text Elements`: ein Eintrag pro Text-Element, Inhalt gefolgt von `^<id>` (Blockreferenz-Anker).
  Bei mehrzeiligem Text die Zeilen 1:1 übernehmen, Anker ans Ende der letzten Zeile.
  Diese Sektion dient Obsidian-Suche/Backlinks — nicht pflicht für korrektes Rendering,
  aber zur Konsistenz immer mitpflegen.
- Der eigentliche Inhalt steht im ` ```json`-Fence unter `## Drawing`, in `%% ... %%` eingebettet.
- **Wichtig:** Das Plugin-Setting `compress: true` (`.obsidian/plugins/obsidian-excalidraw-plugin/data.json`)
  bedeutet, dass bestehende Dateien normalerweise ` ```compressed-json` (LZ-String-kodiert) nutzen.
  Rohes, unkomprimiertes ` ```json` wird aber ebenfalls akzeptiert — Obsidian wandelt die Datei beim
  nächsten Öffnen/Speichern selbst in `compressed-json` um. Das ist kein Fehler und die Datei danach
  nicht zurückkonvertieren, wenn sie sich seit dem letzten Schreiben geändert hat.
- Nach jedem Schreiben mit `scripts/validate_drawing.py` prüfen (kein GUI-Zugriff verfügbar).

## JSON-Grundgerüst

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [ /* Elemente, siehe unten */ ],
  "appState": { "viewBackgroundColor": "#ffffff", "gridSize": null },
  "files": {}
}
```

## Gemeinsame Pflichtfelder für jedes Element

`id, type, x, y, width, height, angle, strokeColor, backgroundColor, fillStyle,
strokeWidth, strokeStyle, roughness, opacity, groupIds, frameId, roundness, seed,
version, versionNonce, isDeleted, boundElements, updated, link, locked`

- `id`: frei wählbarer eindeutiger String (kurze sprechende IDs sind ok, z. B. `"rectA"`).
- `seed`/`versionNonce`: beliebige Ganzzahlen, müssen nur pro Element eindeutig genug sein
  (kollidieren sie mit einem anderen Element, kann Excalidraw die Handzeichnungs-Struktur teilen).
- `roundness`: `{ "type": 3 }` für abgerundete Rechtecke, `{ "type": 2 }` für Pfeile, `null` für Text.
- `isDeleted: false`, `locked: false`, `link: null`, `updated: 1` als Standardwerte ausreichend.

## Rechteck (`type: "rectangle"`)

Zusätzlich zu den Pflichtfeldern keine Extra-Felder nötig. Für Boxen mit Text:
`boundElements: [{ "id": "<textId>", "type": "text" }]` setzen (und ggf. `"type": "arrow"`
für angebundene Pfeile mit auflisten).

## Text (`type: "text"`)

Zusätzliche Felder: `text, fontSize, fontFamily, textAlign, verticalAlign, baseline,
containerId, originalText, lineHeight`.

- `fontFamily: 1` (Handschrift-Font "Virgil", Standard).
- `textAlign`/`verticalAlign`: `"center"/"middle"` wenn in einer Box zentriert, sonst
  `"left"/"top"` für freistehenden Text.
- `containerId`: id der umschließenden Box, oder `null` bei freistehendem Text.
- `text` und `originalText`: identisch setzen, mehrzeilig mit `\n` trennen.
- Breite/Höhe für freistehenden mehrzeiligen Text grob schätzen: `height ≈ Zeilenanzahl * 25`
  (fontSize 20, lineHeight 1.25), `width` nach längster Zeile (~11px/Zeichen). Das Plugin
  korrigiert das beim ersten manuellen Editieren in der App automatisch — nur relevant, damit
  beim ersten Öffnen kein Text abgeschnitten wirkt.

## Pfeil (`type: "arrow"`)

Zusätzliche Felder: `points, lastCommittedPoint, startBinding, endBinding,
startArrowhead, endArrowhead`.

- `points`: relative Koordinaten ab `x`/`y` des Elements, z. B. `[[0,0],[150,0]]` für eine
  gerade horizontale Linie der Länge 150.
- `startBinding`/`endBinding`: `{ "elementId": "<id>", "focus": 0, "gap": 4 }` um den Pfeil an
  eine Box zu binden. Die gebundene Box braucht dafür den Pfeil in ihrem `boundElements`.
- `startArrowhead: null`, `endArrowhead: "arrow"` für einen einseitigen Pfeil.

## Bekannte Stolpersteine

(Bisher keine — erster Test lief fehlerfrei. Neue Punkte hier ergänzen, sobald etwas
schiefgeht, damit sich der Skill mit der Nutzung verbessert.)
