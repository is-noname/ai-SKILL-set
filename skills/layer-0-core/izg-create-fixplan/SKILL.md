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
- Sortierkaskade (deterministisch, jede Stufe nur bei Gleichstand der vorigen):
  1. Schritte, von denen andere Schritte abhaengen, zuerst.
  2. Bei gleicher Abhaengigkeitsstufe: Risiko hoch vor mittel vor niedrig.
  3. Bei weiterem Gleichstand: aufsteigend nach Finding-ID.
- Risikostufen (je mit pruefbarem Kriterium):
  - hoch: oeffentliche API, Datenmodell oder Migration betroffen
  - mittel: geteilte Funktion/Modul mit mehr als einem Aufrufer betroffen
  - niedrig: Aenderung lokal auf eine Funktion begrenzt
- Kleine, einzeln testbare Schritte
- Pro Schritt genau EIN primaeres Ziel
- Keine neuen Features

Ablauf:
1. Findings einlesen
2. Abhaengigkeiten zwischen Findings bestimmen
3. nach Sortierkaskade sortieren
4. Felder pro Schritt ausfuellen
5. Ausgabe schreiben (siehe Ablage)
6. verifizieren (siehe Verifikation)

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

## Wenn etwas fehlschlaegt

| Symptom | Massnahme |
|---|---|
| Keine Findings-Liste in der Anfrage | Nutzer nach der Quelle fragen ("Welcher Report / welche Datei?") und abbrechen — nichts schreiben, kein eigenes Review starten |
| Datei mit Findings nicht lesbar oder leer | Pfad nennen und beim Nutzer rueckfragen, nicht auf eine andere Datei ausweichen |
| Finding ohne genug Kontext fuer `Aenderungen` | Feld als `unklar — Rueckfrage: <konkrete Frage>` fuellen, Schritt trotzdem aufnehmen |
| Kein automatisierbarer Test fuer ein Finding vorhanden | `Test danach: manuelle Pruefung — <was genau anzusehen ist>` schreiben, nie leer lassen |
| Zwei Findings blockieren sich gegenseitig | In einen Schritt zusammenfassen, beide IDs im Feld `Finding-ID` nennen und in der Reihenfolge-Begruendung begruenden |
| `docs/` existiert nicht | Verzeichnis anlegen (`mkdir -p docs`), dann schreiben |
| Zieldatei existiert schon | Nicht ueberschreiben — `## Lauf <YYYY-MM-DDTHH:MM>` anhaengen (siehe Ablage) |
| Schreiben schlaegt fehl (Rechte, Pfad) | Fehler mit Pfad melden, Plan im Chat vollstaendig ausgeben, keinen Ersatzpfad erfinden |

## Verifikation

Nach dem Schreiben pruefen — jede Abweichung korrigieren, bevor der Lauf als fertig gilt:

1. Jede Finding-ID aus der Eingabe kommt in genau einem Schritt vor — keine fehlt, keine doppelt,
   keine erfundene ID dazu.
2. Jeder Schritt hat alle sieben Felder (`Schritt`, `Finding-ID`, `Ziel`, `Aenderungen`, `Risiko`,
   `Test danach`, `Done-Kriterium`) ausgefuellt — kein Platzhalter wie `TBD`, `<...>` oder leer.
3. `Risiko` ist genau einer der Werte `niedrig`, `mittel`, `hoch`.
4. `## Reihenfolge-Begruendung` hat 3-6 Stichpunkte.
5. Die Datei existiert am genannten Pfad und der Fix-Plan dieses Laufs beginnt mit
   `## Fix-Reihenfolge`.

Pruefbefehl (Pfad anpassen):

```bash
test -f docs/fixplan-$(date +%F).md && grep -c '^- Finding-ID:' docs/fixplan-$(date +%F).md
```

Erwartet: Exit-Code 0 und eine Zahl gleich der Anzahl der Schritte.
