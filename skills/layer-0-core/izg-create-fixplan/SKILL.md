---
name: izg-create-fixplan
description: Erstelle einen umsetzbaren Fix-Plan.
disable-model-invocation: true
---

Erstelle einen umsetzbaren Fix-Plan.

Regeln:
- Reihenfolge nach Risiko und Abhaengigkeit
- Kleine, einzeln testbare Schritte
- Pro Schritt genau EIN primaeres Ziel
- Keine neuen Features

Ausgabeformat:
## Fix-Reihenfolge
Pro Schritt genau so:
- Schritt: <nummer>
- Finding-ID: <F-...>
- Ziel: <was nach dem Fix korrekt sein muss>
- Aenderungen: <betroffene dateien/funktionen>
- Risiko: niedrig | mittel | hoch
- Test danach: <genauer Befehl/Testfall>
- Done-Kriterium: <messbares Ergebnis>

## Reihenfolge-Begruendung
- 3-6 Stichpunkte

Ablagepflicht:
- Speichere die Ausgabe als Markdown-Datei
