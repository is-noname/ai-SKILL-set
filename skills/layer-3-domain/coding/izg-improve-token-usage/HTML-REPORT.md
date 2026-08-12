# HTML Report Format

> Nutzt dieselbe redaktionelle Anmutung wie `improve-codebase-architecture`
> (Tailwind stone/slate), aber mit eigenem Akzent: Rot fuer Verbrauch, Gruen fuer
> Ersparnis. Nicht der globale `html-report-template`-Skin — der ist Dark-Mode und
> passt nicht zu den Balken- und Vorher/Nachher-Vergleichen hier.

Der Report ist eine einzelne, eigenstaendige HTML-Datei im Temp-Verzeichnis. Tailwind und Mermaid kommen per CDN. Anders als beim Architektur-Report tragen hier **Zahlen** die Hauptlast, nicht Diagramme: jede Aussage haengt an einem Messwert. Diagramme illustrieren, sie ersetzen die Zahl nicht.

## Scaffold

```html
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <title>Token-Review — {{projektname}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      .bar { height: 1.5rem; border-radius: 2px; }
      .burn { background: #dc2626; }
      .save { background: #059669; }
      .idle { background: #cbd5e1; }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="messung">...</section>
      <section id="kandidaten" class="space-y-10">...</section>
      <section id="hebel">...</section>
    </main>
  </body>
</html>
```

## Header

Projektname, Datum, Anzahl ausgewerteter Sessions. Dazu eine Zeile mit der Datenbasis: *"120 Requests aus 3 Sessions, Cache-Trefferquote 97,6 %"*. Kein Einleitungsabsatz.

Wenn keine Transcripts vorlagen: rot getoenter Kasten, eine Zeile — *"Keine Messdaten. Alle Kandidaten sind statisch geschaetzt."*

## Messungs-Abschnitt

Steht **vor** den Kandidaten. Er ist die Beweislage, auf die sich jede Karte beruft.

- **Verbrauchsbalken** — horizontale Balken pro Tool, Breite proportional zur Kontextlast, Zahl rechts. Reine Divs mit `.bar.burn`, kein Mermaid.
- **Cache-Kachel** — Trefferquote gross, darunter eine Zeile Einordnung. Unter 85 % rot einfaerben mit dem Hinweis auf Cache-Bruch.
- **Wiederholungstabelle** — die mehrfach ausgefuehrten Aufrufe, Spalten: Wiederholungen, Tokens, Aufruf (`font-mono text-xs`, umbruchsicher mit `break-all`).

## Kandidaten-Karte

Ein `<article>` pro Kandidat. Die Zahl steht oben, nicht versteckt im Fliesstext.

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

Zwei Balken untereinander, gleiche Skala: Vorher in `.burn`, Nachher in `.save`, die Differenz beschriftet. Funktioniert fuer fast jeden Kandidaten und ist sofort lesbar.

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

Eine Reihe Kaestchen, eins pro Turn. Vorher: bei jedem Turn ein roter Block (Neuberechnung). Nachher: ein roter Block, danach nur graue (Cache-Treffer). Zeigt Kosten, die sich ueber die Session akkumulieren.

### Mermaid-Flow (fuer Ablaeufe und Subagent-Spawns)

Wenn der Kandidat ein Ablauf ist — Spawn, der einen Spawn ausloest; Hook, der ein Skript ruft, das eine Datei kippt — dann `flowchart` mit Token-Beschriftung an den Kanten. Verbrauchspfade rot einfaerben.

```html
<div class="rounded-lg border border-slate-200 bg-white p-4">
  <pre class="mermaid">
    flowchart LR
      A[Sessionstart] -->|"1.200 tok"| B[Repo-Scan]
      B -->|"3.400 tok"| C[Alle Tickets lesen]
      classDef burn stroke:#dc2626,stroke-width:2px;
      class B,C burn
  </pre>
</div>
```

### Preload-Stapel (fuer SKILL.md- und CLAUDE.md-Splits)

Vorher: ein hoher Block, komplett eingefaerbt — alles im Preload. Nachher: ein kleiner eingefaerbter Sockel (Kernanweisung) plus mehrere blasse Bloecke darueber, die als "auf Abruf" beschriftet sind.

## Stil

- Redaktionell, kein Dashboard. Grosszuegiger Weissraum. Zahlen monospaced, Prosa serifenlos.
- Farbe sparsam: Rot fuer Verbrauch, Gruen fuer Ersparnis, Amber fuer Abwaegung. Sonst stone/slate.
- Balken nie hoeher als `h-6` — es ist ein Report, kein Balkendiagramm-Poster.
- Diagramme ~280 px hoch, damit Vorher/Neben nebeneinander ohne Scrollen passt.
- Einzige Skripte sind Tailwind-CDN und Mermaid-Import. Sonst statisch.

## Abschnitt "Groesster Hebel"

Eine groessere Karte: Kandidatenname, die Ersparniszahl, ein Satz Begruendung, Ankerlink zur Karte. Mehr nicht.

## Ton

Knappes Deutsch. Die Nomen und Verben kommen aus dem Vokabular in `SKILL.md`.

**Genau so verwenden:** Tokenfresser, Kontextlast, Redundanz, Cache-Bruch, Preload, Lazy Load, Turn-Kosten, Ertrag.

**Nie ersetzen durch:** Performance, Effizienz, Optimierung, Overhead, Bloat (fuer Tokenfresser) · Speicher, Payload (fuer Kontextlast) · Doppelung, Duplikat (fuer Redundanz).

**Passende Formulierungen:**

- "Der Sessionstart-Scan kostet 3.400 Tokens Kontextlast, bevor der User etwas gefragt hat."
- "Redundanz: dieselbe Ticketregel steht in globaler CLAUDE.md und in der SKILL.md."
- "Cache-Bruch durch den Zeitstempel in Zeile 3 — jeder Turn zahlt den Prefix neu."
- "Ertrag: 8.000 Tokens Subagent fuer drei Zeilen, die ein grep geliefert haette."

**Ersparnis-Angaben** immer mit Bezugsgroesse: *pro Session*, *pro Turn*, *pro Woche*. Nie "spart viel" oder "deutlich weniger" — wenn die Zahl fehlt, gehoert die Karte als `Spekulativ` markiert oder gar nicht in den Report.

Kein Herumdrucksen, keine Einleitungssaetze. Was ein Aufzaehlungspunkt sein kann, wird einer. Was gestrichen werden kann, wird gestrichen.
