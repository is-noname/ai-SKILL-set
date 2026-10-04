---
name: izg-excalidraw-chuck
description: This skill should be used when the user asks to create, extend, or update an Excalidraw diagram/drawing/visualization inside the Obsidian vault "Chuck" (fixed path /home/izg/Dokumente/AI/00_chuck/Chuck/Excalidraw/) — e.g. cashflow structures, wealth/budget overviews, decision trees, or profile/role diagrams for CFO, banker, broker, CEO, or CTO. Not for diagrams outside this vault.
---

# Excalidraw Chuck Vault

## Overview

Erzeugt und erweitert Excalidraw-Diagramme direkt als `.md`-Dateien für das
obsidian-excalidraw-plugin im Vault "Chuck" (`/home/izg/Dokumente/AI/00_chuck/Chuck/`).
Kein externes Rendering-Tool nötig — die Datei wird per Write/Edit geschrieben, Obsidian
übernimmt Anzeige und spätere Bearbeitung durch den Nutzer.

Getestet am 2026-08-28: 2-Boxen-Diagramm mit Pfeil und mehreren mehrzeiligen Textblöcken
hat beim ersten Versuch fehlerfrei gerendert (`Chuck/Excalidraw/CFO-Test-Diagramm.md`).

## Workflow

1. **Zielort festlegen**: neue Datei unter `Chuck/Excalidraw/<sprechender-name>.md`, oder
   bestehende Datei in diesem Ordner erweitern (bestehende Elemente erhalten, neue ergänzen —
   nicht überschreiben, außer explizit gewünscht).
2. **Format nachschlagen**: `references/element_schema.md` enthält das vollständige Datei-
   und JSON-Schema (Frontmatter, Text-Elements-Sektion, Pflichtfelder pro Element-Typ für
   Rechteck/Text/Pfeil, Layout-Faustregeln für Textgröße). Bei jedem Diagramm dort
   nachschlagen statt Felder zu raten.
3. **Datei schreiben**: mit Write (neue Datei) oder Edit (Ergänzung) im rohen
   ` ```json`-Format — nicht `compressed-json` selbst erzeugen, das übernimmt Obsidian beim
   nächsten Öffnen automatisch.
4. **Validieren**: `scripts/validate_drawing.py <pfad>` ausführen. Ohne "OK" nicht als
   erledigt melden.
5. **Rückmeldung einholen**: da kein GUI-Zugriff besteht, den Nutzer bitten, die Datei in
   Obsidian zu öffnen und Platzierung/Rendering zu bestätigen — besonders bei mehrzeiligem
   Text (geschätzte Breite/Höhe) oder vielen Elementen (Überlappung).
6. **Stolpersteine festhalten**: geht beim Rendern etwas schief, den Fund + Fix in
   `references/element_schema.md` unter "Bekannte Stolpersteine" ergänzen, damit der Skill
   mit der Nutzung besser wird.

## Inhaltliche Grundlage für Rollen-/Profil-Diagramme

Wenn ein Diagramm Rollen/Erwartungen zwischen den Agents darstellen soll, Inhalte aus den
jeweiligen Projektregeln ableiten, nicht frei erfinden. Alle Projekte liegen als
Geschwisterordner unter `/home/izg/Dokumente/AI/00_chuck/`, daher von jedem Projekt aus
per `../<projekt>/...` erreichbar:
- CFO-Profil: `../CFO/claude.md`
- banker-Rolle/Grenzen: `../banker/AGENTS.md` (§ Rolle: Finanzberatung)
- broker-Rolle/Grenzen: `../broker/AGENTS.md` (§ Standardrolle, § Broker-Prioritäten)
- CEO-/CTO-Profil: `../CEO/CLAUDE.md`, `../CTO/CLAUDE.md`

Für das eigene Profil (des Projekts, in dem dieser Skill gerade läuft) die lokale
`CLAUDE.md`/`claude.md`/`AGENTS.md` ohne `../`-Präfix lesen.

## Resources

- `references/element_schema.md` — vollständiges Datei-/JSON-Schema, Pflichtfelder,
  Layout-Faustregeln, Stolperstein-Log.
- `scripts/validate_drawing.py` — prüft eine Diagramm-Datei auf gültiges JSON, Pflichtfelder
  und doppelte IDs, bevor sie als fertig gemeldet wird.
