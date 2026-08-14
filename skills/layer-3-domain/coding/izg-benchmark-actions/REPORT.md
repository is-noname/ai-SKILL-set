# HTML Report Format

> Gleiche redaktionelle Anmutung wie `izg-improve-token-usage` (Tailwind stone/slate),
> aber andere Farblogik: dort Rot fuer Verbrauch und Gruen fuer Ersparnis, hier
> **eine Farbe pro Variante**, ueber den ganzen Report durchgehalten. Es wird nichts
> "gespart", es wird verglichen.

Eine einzelne, eigenstaendige HTML-Datei im Temp-Verzeichnis, damit nichts im Repo landet. Pfad aus `$TMPDIR` aufloesen, Fallback `/tmp`, Dateiname `<tmpdir>/benchmark-<task>-<timestamp>.html`. Danach oeffnen (`xdg-open` / `open` / `start`) und dem User den absoluten Pfad nennen.

Datenquelle ist ausschliesslich `bench.py compare --json`. Keine Zahl im Report, die nicht dort steht.

## Scaffold

```html
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <title>Benchmark — {{task}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      .bar { height: 1.5rem; border-radius: 2px; }
      .v1 { background: #0f766e; }
      .v2 { background: #b45309; }
      .v3 { background: #6d28d9; }
      .span { background: repeating-linear-gradient(90deg,#cbd5e1 0 4px,transparent 4px 8px); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="urteil">...</section>
      <section id="vergleich">...</section>
      <section id="varianten" class="space-y-8">...</section>
      <section id="versuchsaufbau">...</section>
    </main>
  </body>
</html>
```

## Header

Task-Kennung, Datum, Modell, Anzahl Laeufe je Variante. Eine Zeile Datenbasis: *"3 Varianten x 5 Laeufe, Modell claude-opus-5, Gewichtung input x1 / cache_creation x1,25 / cache_read x0,1 / output x5"*. Kein Einleitungsabsatz.

## Urteil — steht oben

Anders als beim Token-Review kommt das Ergebnis **zuerst**, nicht zum Schluss. Eine grosse Karte:

- Ein Satz, gross gesetzt: *"`mit-skill` ist um 34 % guenstiger bei gleichem Ertrag."*
- Darunter klein die Belastbarkeit: *"n=5 je Variante, Spannen getrennt, alle Laeufe `ok`."*

Bei ueberlappenden Spannen wird der Satz genauso gross gesetzt: *"Kein belastbarer Unterschied."* Kein kleingedrucktes Ausweichen auf Mediane, keine amber getoente Hoffnung. Ein Nullergebnis ist ein Ergebnis.

## Vergleichs-Abschnitt

- **Spannenbalken** — eine Zeile pro Variante, gleiche Skala. Der Balken deckt Minimum bis Maximum ab (`.span`, gestrichelt), darauf ein voller Block in der Variantenfarbe am Median. So sieht man auf einen Blick, ob sich Spannen ueberlappen — genau das Kriterium, an dem das Urteil haengt.
- **Kennzahlentabelle** — Spalten: Variante, n, Median gewichtet, Spanne, Kosten $ Median, Turns Median, Cache-Quote, Ertrag. Zahlen `font-mono`, rechtsbuendig. Die Basis-Variante mit `bg-slate-100` unterlegen.
- **Ertragsspalte nie weglassen.** Ein Report ohne Ertrag ist eine Kostenaufstellung, kein Benchmark.

## Variantenkarte

Ein `<article>` pro Variante, nur wenn es etwas zu erklaeren gibt (auffaellige Streuung, abweichendes Tool-Profil, ein `partial`-Lauf).

- **Titel** — Variantenname plus Einordnung in einem Halbsatz.
- **Tool-Profil** — welche Tools wie oft, und wie viel Kontextlast sie gebracht haben. Zeigt, *wo* der Unterschied herkommt: mehr Reads, ein Subagent-Spawn, ein Skript mit ausuferndem Output.
- **Streuungshinweis** — wenn Maximum > 2x Minimum: eine Zeile dazu, welcher Lauf ausreisst und warum (aus dem Laufdatensatz, nicht geraten).
- **Ertragsnotizen** — die `note`-Felder der Laeufe, die nicht `ok` sind. Woertlich.

Keine Erklaerabsaetze. Wenn eine Karte einen Absatz braucht, fehlt ihr die richtige Zahl.

## Versuchsaufbau — steht unten

Damit der Vergleich nachvollziehbar bleibt: Testaufgabe im Wortlaut (`<pre>`, umbruchsicher), `--setup`-Kommandos je Variante, Modell, Permission-Mode, Datum, Ablage der Laufdaten. Zusammengeklappt in einem `<details>`, aufklappbar.

## Stil

- Redaktionell, kein Dashboard. Grosszuegiger Weissraum. Zahlen monospaced, Prosa serifenlos.
- **Farbe kodiert die Variante, sonst nichts.** Kein Rot fuer "schlecht" — eine teurere Variante kann die richtige sein.
- Balken nie hoeher als `h-6`.
- Einziges Skript ist der Tailwind-CDN. Mermaid wird hier nicht gebraucht; die Aussage steckt in Balken und Tabelle.

## Ton

Knappes Deutsch. Nomen und Verben aus dem Vokabular in `SKILL.md`.

**Genau so verwenden:** Testaufgabe, Variante, Lauf, gewichtete Tokens, Spanne, Ertrag, Basis, Urteil.

**Nie ersetzen durch:** Score, Rating, Punktzahl, Performance, Effizienz, Gewinner, Sieger.

**Passende Formulierungen:**

- "`mit-skill` liegt im Median bei 41.200 gewichteten Tokens, Spanne 38.900–44.100."
- "Der Unterschied kommt aus den Reads: 14 gegen 4 bei gleicher Aufgabe."
- "Lauf 3 reisst aus — ein Subagent-Spawn, den kein anderer Lauf hatte."
- "Kein belastbarer Unterschied. Die Entscheidung faellt nicht ueber Tokens."

Prozentangaben nur, wenn `compare` sie ausgibt. Nie "deutlich guenstiger" oder "spuerbar schneller" — wenn die Spannen ueberlappen, gibt es keinen Unterschied zu berichten.
