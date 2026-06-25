# Dokument-ID Konvention

> Diese Datei wird von `scripts/init_tickets.sh` in neue Projekte deployt.
> In `CLAUDE.md` einbinden damit Claude die Konvention bei jedem Session-Start kennt:
> ```markdown
> @docs/doc-ids.md
> ```
> Projekt-Kürzel in der Tabelle unten beim ersten Einsatz eintragen — diese Datei ist die einzige Kürzel-Registry für das Projekt.

## Schema

```
{TYPE}-{YYYYMMDD}-{SEQ}_{Beschreibung}.md
```

**Gleiche SEQ = gleiche Themen-Kette** (z.B. AUD-001 und die daraus abgeleiteten Tickets gehören zusammen)

## Projekt-Kürzel

Projekt-Kürzel werden pro Repo vergeben und hier gepflegt.
Claude trägt beim ersten Einsatz in einem neuen Projekt das Kürzel ein — diese Datei ist die einzige Kürzel-Registry für dieses Repo.

| Kürzel | Projekt |
|--------|---------|
| `IZG` | ai-SKILL-set |

## Typ-Codes

| Code | Bedeutung |
|------|-----------|
| `AUD` | Audit |
| `RPT` | Report / Analyse |
| `RFC` | Konzept / Framework-Entwurf |
| `BT` | Backtesting-Plan oder -Report |
| `ADR` | Architectural Decision Record — nicht-offensichtliche Entscheidung mit Trade-off |

**Nicht mehr als doc-ids:** `FIX`, `FIXR`, `TODO` — diese werden als Tickets erfasst (`tickets/open/`).

**ADR-Eingangsfilter** — nur erstellen wenn alle drei zutreffen:
1. Schwer rückgängig zu machen
2. Ohne Kontext überraschend (ein künftiger Leser würde fragen „warum so?")
3. Echtes Trade-off gegen konkrete Alternativen

## Beispiele

```
AUD-20260301-001_Signal_Combination_Logic.md
RFC-20260115-001_Pattern_Detection_Redesign.md
ADR-20260625-001_Counter_statt_grep.md
```

## Sonderfall: CONTEXT.md

Lebendes Glossar — **kein doc-ids-Typ, kein Datum, keine SEQ-Nummer**.
Liegt im Repo-Root.

## Ablage

```
docs/
├── {YYYYMMDD}-{SEQ}_{Beschreibung}/
│   └── {TYPE}-{YYYYMMDD}-{SEQ}_{Beschreibung}.md
└── archiv/
```
