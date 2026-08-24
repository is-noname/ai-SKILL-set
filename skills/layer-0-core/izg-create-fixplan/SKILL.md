---
name: izg-create-fixplan
description: Erstelle einen umsetzbaren Fix-Plan aus einer Findings-Liste. Use when nach einem Review oder Audit die Findings in eine abgearbeitete Reihenfolge gebracht werden sollen.
layer: 0
dependencies: []
disable-model-invocation: true
---

Erstelle einen umsetzbaren Fix-Plan.

Eingabe:
Eine Liste von Findings mit IDs im Format `F-<n>` — typischerweise aus einem Review-,
Audit- oder KISSD-Report, entweder direkt im Prompt oder als Datei, auf die der Nutzer
zeigt. Die `Finding-ID` im Ausgabeformat wird aus dieser Liste uebernommen, nie erfunden.

- Keine Findings-Liste vorhanden: nicht raten und nicht selbst ein Review fahren.
  Den Nutzer nach der Quelle fragen ("Welcher Report / welche Datei enthaelt die
  Findings?") und hier abbrechen.
- Findings ohne IDs gegeben: in der Reihenfolge, in der sie dastehen, selbst
  durchnummerieren als `F-1`, `F-2`, ... und im Report unter der Fix-Reihenfolge
  vermerken: "Findings waren unnummeriert, IDs in Eingabereihenfolge vergeben."
- Findings mit einem anderen ID-Schema (z.B. `K1`, `SEC-03`): die vorhandenen IDs
  unveraendert uebernehmen, nicht auf `F-<n>` umschreiben.

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

## Ablage
Schreibe die Ausgabe nach `docs/fixplan-<YYYY-MM-DD>.md` im Projekt-Root
(Datum des Laufs, nicht des Findings-Reports).
- Existiert `docs/` nicht: Verzeichnis anlegen.
- Existiert die Zieldatei bereits: nicht ueberschreiben, sondern einen neuen
  Abschnitt `## Lauf <YYYY-MM-DDTHH:MM>` mit dem vollstaendigen Fix-Plan
  dieses Laufs anhaengen.
