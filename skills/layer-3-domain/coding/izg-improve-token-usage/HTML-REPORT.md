# HTML Report Format

> Nutzt dieselbe redaktionelle Anmutung wie `improve-codebase-architecture`
> (Tailwind stone/slate), aber mit eigenem Akzent: Rot fuer Verbrauch, Gruen fuer
> Ersparnis. Nicht der globale `html-report-template`-Skin — der ist Dark-Mode und
> passt nicht zu den Balken- und Vorher/Nachher-Vergleichen hier.

Scaffold, Header und Messungs-Abschnitt schreibt `scripts/render_html()`
(`analyze_transcript.py --html`). Dieser Skill fuellt nur noch die zwei leeren
Container, die das Skript im Output laesst: `#kandidaten` und `#hebel`. Anders
als beim Architektur-Report tragen hier **Zahlen** die Hauptlast, nicht
Diagramme: jede Aussage haengt an einem Messwert. Diagramme illustrieren, sie
ersetzen die Zahl nicht.

## Kandidaten-Karte

Ein `<article>` pro Kandidat, in `#kandidaten`. Die Zahl steht oben, nicht versteckt im Fliesstext.

- **Titel** — benennt die Massnahme, nicht das Problem (z. B. "Sessionstart-Scan durch Ansage ersetzen").
- **Badge-Zeile** — Trade-off (`Eindeutig` = emerald, `Abwaegung` = amber, `Spekulativ` = slate) plus ein Tag fuer die Kategorie (`Preload`, `Redundanz`, `Skript-Output`, `Subagent`, `Cache`, `MCP`).
- **Messwert-Leiste** — die belegende Zahl, gross und monospaced. Darunter klein die Quelle: *"3 Sessions, 12 Aufrufe"*. Ohne Messung stattdessen `Unbelegt` als graues Badge.
- **Stellen** — Dateiliste, `font-mono text-sm`.
- **Problem** — ein Satz. Was Tokens frisst.
- **Loesung** — ein Satz. Was sich aendert.
- **Ersparnis** — eine Zeile mit Rechenweg: *"1.400 Tokens x 8 Sessions/Woche = ~11.000/Woche"*. Nie eine nackte Zahl ohne Herleitung.
- **Vorher/Nachher** — zwei Spalten, siehe Muster unten.
- **Kosten der Massnahme** (nur bei `Abwaegung`) — amber getoente Zeile: was verloren geht.

Keine Erklaerabsaetze. Wenn eine Karte einen Absatz braucht, fehlt ihr die richtige Zahl.

## Diagramm-Muster

Passendes Muster waehlen, mischen. Nicht jede Karte gleich aussehen lassen.

### Balkenvergleich (Standardfall)

Zwei Balken untereinander, gleiche Skala: Vorher in `.burn`, Nachher in `.save`, die Differenz beschriftet (Klassen aus dem Scaffold, siehe `render.py`). Funktioniert fuer fast jeden Kandidaten und ist sofort lesbar.

```html
<div class="space-y-2">
  <div class="flex items-center gap-3">
    <span class="w-20 text-xs uppercase tracking-wider">Vorher</span>
    <div class="bar burn" style="width: 78%"></div>
    <span class="font-mono text-sm">4.200</span>
  </div>
  <div class="flex items-center gap-3">
    <span class="w-20 text-xs uppercase tracking-wider">Nachher</span>
    <div class="bar save" style="width: 12%"></div>
    <span class="font-mono text-sm">650</span>
  </div>
</div>
```

### Turn-Verlauf (fuer Cache-Bruch und wiederholte Reads)

Eine Reihe Kaestchen, eins pro Turn. Vorher: jeder Turn ein roter Block (Neuberechnung). Nachher: ein roter Block, danach nur graue (Cache-Treffer).

### Mermaid-Flow (fuer Ablaeufe und Subagent-Spawns)

Wenn der Kandidat ein Ablauf ist — Spawn, der einen Spawn ausloest; Hook, der ein Skript ruft, das eine Datei kippt — dann `flowchart LR` mit Token-Beschriftung an den Kanten (`-->|"1.200 tok"|`), Verbrauchspfade per `classDef` rot einfaerben. In `<pre class="mermaid">`.

### Preload-Stapel (fuer SKILL.md- und CLAUDE.md-Splits)

Vorher: ein hoher, komplett eingefaerbter Block (alles im Preload). Nachher: kleiner Sockel (Kernanweisung) plus blasse Bloecke darueber, "auf Abruf" beschriftet.

## Stil

- Redaktionell, kein Dashboard. Grosszuegiger Weissraum. Zahlen monospaced, Prosa serifenlos.
- Farbe sparsam: Rot fuer Verbrauch, Gruen fuer Ersparnis, Amber fuer Abwaegung. Sonst stone/slate.
- Balken nie hoeher als `h-6`.
- Diagramme ~280 px hoch, damit Vorher/Nachher nebeneinander ohne Scrollen passt.

## Abschnitt "Groesster Hebel"

In `#hebel`. Eine groessere Karte: Kandidatenname, die Ersparniszahl, ein Satz Begruendung, Ankerlink zur Karte. Mehr nicht.

## Ton

Knappes Deutsch. Die Nomen und Verben kommen aus dem Vokabular in `SKILL.md`.

**Genau so verwenden:** Tokenfresser, Kontextlast, Redundanz, Cache-Bruch, Preload, Lazy Load, Turn-Kosten, Ertrag.

**Nie ersetzen durch:** Performance, Effizienz, Optimierung, Overhead, Bloat (fuer Tokenfresser) · Speicher, Payload (fuer Kontextlast) · Doppelung, Duplikat (fuer Redundanz).

**Ersparnis-Angaben** immer mit Bezugsgroesse: *pro Session*, *pro Turn*, *pro Woche*. Nie "spart viel" oder "deutlich weniger" — wenn die Zahl fehlt, gehoert die Karte als `Spekulativ` markiert oder gar nicht in den Report.

Kein Herumdrucksen, keine Einleitungssaetze. Was ein Aufzaehlungspunkt sein kann, wird einer.
