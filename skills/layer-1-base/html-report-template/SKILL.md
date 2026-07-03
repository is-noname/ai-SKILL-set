---
name: html-report-template
description: Generisches CSS-Skin für selbstständige HTML-Reports (Dark Mode, Desktop-first) auf Basis der globalen Design Tokens. Kein Struktur-Skeleton — nur Variablen und Basis-Komponenten (Cards, Tabellen, Tags, Stat-Grid), die jeder Report-Skill frei anordnet. Use when ein HTML-Report/Dashboard/Analyse-Output erstellt wird und dabei konsistent zu anderen Reports aussehen soll statt eigene Farben/Abstände zu erfinden.
layer: 1
dependencies: []
---

# HTML Report Template

Ein **Skin, kein Skeleton**: dieses Skill definiert CSS-Variablen und Basis-Komponenten,
keine feste HTML-Struktur (Header/Sections/Footer). Jeder Report-Skill baut seine eigene
Struktur (siehe z.B. `layer-3-domain/coding/improve-codebase-architecture/HTML-REPORT.md`
für ein sehr spezifisches Format mit Mermaid-Diagrammen) — aber alle greifen auf dieselben
Farb-/Typografie-/Spacing-Werte zu, statt sie neu zu erfinden.

Quelle der Werte: `~/.claude/design-tokens.md` (globale Design Tokens für Web, CLI, Apps,
Reports). Dieses Skill übersetzt sie in ein direkt einbindbares CSS-Snippet für
selbstständige (self-contained) HTML-Dateien ohne Build-Step.

## Wann nutzen

- Neuer HTML-Report/Dashboard, der als einzelne `.html`-Datei ausgeliefert wird
  (kein Framework, keine externen Stylesheets außer optional CDN-Fonts)
- Wenn Konsistenz mit anderen Reports/Tools des Users gewünscht ist (Dark Mode,
  Canto-Green-Akzent, Manrope-Typografie)

## Wann nicht nutzen

- Interaktive Web-Apps mit eigenem Design-System — dort gelten die App-eigenen Tokens
- Reports mit einem bereits etablierten, sehr spezifischen Format (z.B.
  `improve-codebase-architecture`'s Mermaid/Editorial-Stil) — dort nur die Farbwerte
  übernehmen, nicht die Komponenten-Patterns erzwingen

## CSS-Variablen (aus design-tokens.md)

In den `<head>` einbinden:

```html
<style>
  :root {
    /* Akzent */
    --accent: #06fc99;
    --accent-dim: rgba(6, 252, 153, .07);
    --accent-bg: rgba(6, 252, 153, .13);

    /* Dark-Mode-Ebenen */
    --bg: #111111;
    --surface: #191919;
    --raised: #212121;
    --topbar-bg: #0c0c0c;

    /* Borders */
    --border: #272727;
    --border-mid: #363636;
    --border-hi: #484848;

    /* Text */
    --text: #ededed;
    --muted: #888888;
    --faint: #525252;

    /* Status */
    --red: #f87171;
    --red-bg: rgba(180, 58, 58, .18);
    --red-border: #6b2222;
    --yellow: #fbbf24;
    --yellow-bg: rgba(217, 119, 6, .15);
    --blue: #60a5fa;

    /* Radius */
    --r: 6px;
    --r-sm: 3px;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Manrope', 'Segoe UI', sans-serif;
    font-size: 13px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }

  code, pre, .mono {
    font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  }
</style>
```

Für Fonts (optional, CDN): Google Fonts `Manrope:400,500,600,700,800` und
`JetBrains+Mono`. Falls die Report-Datei komplett offline/self-contained sein muss,
Fallback-Stack (`'Segoe UI', sans-serif` bzw. `Consolas, monospace`) reicht ohne CDN.

## Basis-Komponenten

### Listen / Tabellen (Rows)

```html
<div style="border:1px solid var(--border); border-radius:var(--r); overflow:hidden;">
  <div style="padding:8px 12px; border-bottom:1px solid var(--border); background:var(--surface);">Row 1</div>
  <div style="padding:8px 12px; background:var(--surface);">Letzte Row — kein border-bottom</div>
</div>
```

Hover (falls interaktiv): `background: var(--raised)`. Nie Card-per-Item mit eigenem
`border-radius` stapeln — wirkt "bubblig".

### Stats-Grid (Metabar)

```html
<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(110px, 1fr));
            gap:1px; background:var(--border); border-radius:var(--r); overflow:hidden;">
  <div style="background:var(--surface); padding:14px 16px;">
    <div style="color:var(--muted); font-size:11px;">Label</div>
    <div style="font-size:1.5rem; font-weight:700;">42</div>
  </div>
</div>
```

Border als Gap-Farbe (`gap:1px; background:var(--border)`), kein separater
Border-Trick pro Zelle.

### Tags / Badges

```html
<span style="padding:2px 7px; border-radius:var(--r-sm); font-size:10px; font-weight:700;
             background:var(--accent-bg); color:var(--accent);">OK</span>
<span style="padding:2px 7px; border-radius:var(--r-sm); font-size:10px; font-weight:700;
             background:var(--red-bg); color:var(--red); border:1px solid var(--red-border);">FEHLER</span>
```

### Card-Nesting

Max 1 Ebene: Section-Heading + flache Rows, oder eine Card mit flachen Rows.
Nie: card → card-header → card-body → setting-row → item-card.

## Spacing-Referenz

- Content-Padding: `20px 24px`
- Row-Padding: `8px 12px`
- Card-Body: `12px 14px`
- Card-Header: `10px 14px`
- Sektionsabstand: `margin: 18px 0 8px`
- Max-Width Panels: `1060px` (Desktop-first, verhindert dass Tabellen auf breiten
  Monitoren leer wirken)

## Referenzimplementierungen

- `layer-3-domain/coding/improve-codebase-architecture/HTML-REPORT.md` — nutzt ein
  eigenes Editorial-Farbschema (Tailwind stone/slate/emerald), **nicht** auf dieses
  Skin umgestellt. Kandidat für spätere Migration der Farbwerte, aber die
  Mermaid/Card-Struktur bleibt eigenständig.

## Update-Pfad

Diese Werte sind eine Kopie aus `~/.claude/design-tokens.md`, keine Live-Referenz —
bei Änderungen dort manuell nachziehen, bis [[IZG-T-054]] (Single-Source-of-Truth
für gemeinsame Konventionsdateien) geklärt ist.
