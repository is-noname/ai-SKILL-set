# Design Tokens

Globale Designwerte für alle Outputs (Web, CLI, Apps, Reports).

## Farben — Basis

| Token | Wert | Verwendung |
|-------|------|------------|
| **Akzent (Canto Green)** | `#06fc99` | Buttons, Links, Focus, Highlights |
| Accent dim | `rgba(6,252,153,.07)` | Active-State Hintergrund (Nav, Chips) |
| Accent bg | `rgba(6,252,153,.13)` | Stärkere Akzent-Flächen (Badges, Tags) |

## Farben — Dark Mode Ebenen

3 Hintergrund-Ebenen, keine weiteren:

| Token | Wert | Verwendung |
|-------|------|------------|
| `--bg` | `#111111` | Seitengrund, Sidebar |
| `--surface` | `#191919` | Cards, Rows, Listen |
| `--raised` | `#212121` | Hover-States, Card-Header, erhöhte Elemente |
| `--topbar-bg` | `#0c0c0c` | Topbar (klar dunkler als alles andere) |

## Farben — Borders

| Token | Wert | Verwendung |
|-------|------|------------|
| `--border` | `#272727` | Standard-Rahmen (Cards, Rows) |
| `--border-mid` | `#363636` | Stärkere Trennlinien, Inputs, Tags |
| `--border-hi` | `#484848` | Hover-Border, fokussierte Elemente |

## Farben — Text

Nur 3 Stufen:

| Token | Wert | Verwendung |
|-------|------|------------|
| `--text` | `#ededed` | Primärer Text, Überschriften |
| `--muted` | `#888888` | Sekundärer Text, Labels, Beschreibungen |
| `--faint` | `#525252` | Tertiärer Text, Pfade, Platzhalter, Mono-Meta |

## Farben — Status

| Token | Wert | Verwendung |
|-------|------|------------|
| `--red` | `#f87171` | Fehler-Text |
| `--red-bg` | `rgba(180,58,58,.18)` | Fehler-Badge Hintergrund |
| `--red-border` | `#6b2222` | Fehler-Banner Rahmen |
| `--yellow` | `#fbbf24` | Warn-Text |
| `--yellow-bg` | `rgba(217,119,6,.15)` | Warn-Badge Hintergrund |
| `--blue` | `#60a5fa` | Info, sekundäre Datenreihen |

## Typografie

- **Font:** `'Manrope', 'Segoe UI', sans-serif` (Google Fonts: Manrope 400/500/600/700/800)
- **Mono:** `'JetBrains Mono', 'SF Mono', Consolas, monospace`
- **Base:** 13px / 1.5 line-height, `-webkit-font-smoothing: antialiased`
- **Größen-Skala:** 11px (min) · 12px · 13px (body) · 15px · 1.4–1.6rem (Stat-Werte)
- **Kein Text unter 11px**

## Radius & Animation

- **`--r`:** `6px` (Cards, Modals, Tabellen-Container)
- **`--r-sm`:** `3px` (Inline-Tags, Badges, Inputs, Buttons)
- **Dots/Avatare:** `50%`
- **Transition:** `all .15s ease`

## Spacing

- **Content-Padding:** `20px 24px`
- **Row-Padding:** `8px 12px`
- **Card-Body:** `12px 14px`
- **Card-Header:** `10px 14px`
- **Gap in Item-Grids:** `6px`
- **Sektionsabstand:** `margin: 18px 0 8px`

## Komponenten-Muster (Desktop-Tools)

Desktop-first. Kein Mobile-First.

### Content-Breite
- **Max-Width Panels:** `1060px` — verhindert dass Rows/Tabellen auf breiten Monitoren leer wirken
- Grids füllen die 1060px mit `auto-fill`

### Listen / Tabellen
- Container: `border: 1px solid var(--border); border-radius: var(--r); overflow: hidden`
- Rows: `padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--surface)`
- Letzter Row: kein `border-bottom`
- Hover: `background: var(--raised)`
- **Nie:** Card-per-item mit eigenem border-radius-Stack → "bubbliger Stapel"-Look

### Stats-Grid (Metabar)
- `display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr))`
- `gap: 1px; background: var(--border)` — Border als Gap-Farbe, kein separater Border-Trick
- Zellen: `background: var(--surface); padding: 14px 16px`

### Navigation (Sidebar)
- Active-State: Pill — `background: var(--accent-dim); color: var(--accent); border-radius: var(--r-sm)`
- Kein `border-left`-Trick
- Nav-Items: `margin: 1px 8px; padding: 7px 10px`

### Tags / Badges
- Inline-Tags (ALLOW, DENY, Matcher): `padding: 2px 7px; border-radius: var(--r-sm); font-size: 10px; font-weight: 700`
- Inline-Tags mit sichtbarem Border: `border: 1px solid var(--border-mid)`
- Nav-Badges: `padding: 1px 6px; border-radius: 10px; font-size: 10px`

### Card-Nesting
- Max 1 Ebene: section-heading + flat-rows ODER Card mit flat-rows
- Nie: card → card-header → card-body → setting-row → item-card

### Grid-Spaltenbreiten
- Item-Cards (Agents, Skills): `minmax(200px, 1fr)`
- Memory-Cards: `minmax(260px, 1fr)`
- Workspace-Cards: `minmax(380px, 1fr)`
