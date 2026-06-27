# Dokument-ID Konvention

> Diese Datei ist die **globale Konventions-Quelle** für Dokument-IDs. Sie liegt im
> Verzeichnis deines AI-Agenten (`~/.claude`, `~/.codex`, `~/.gemini`, `~/.vibe`), wird
> per `scripts/setup_global_conventions.sh` dorthin deployt und in der Agent-Konfig
> (`CLAUDE.md` / `AGENTS.md` / …) eingebunden:
> ```markdown
> @doc-ids.md
> ```
> Die projekt-spezifischen Kürzel sind **kein** Teil dieser Konvention — sie leben in
> der separaten Registry `@project-identifier.md` (siehe „Projekt-Kürzel"), die bei
> Updates nie überschrieben wird. Global = Konvention, Registry = User-State.

## Schema

```
{TYPE}-{YYYYMMDD}-{SEQ}_{Beschreibung}.md
```

**Gleiche SEQ = gleiche Themen-Kette** (z.B. AUD-001 und die daraus abgeleiteten Tickets gehören zusammen)

## Projekt-Kürzel

Die Registry der Kürzel pro Projekt ist **user-spezifischer State** und wird bei
Konventions-Updates nie überschrieben. Sie liegt in der separaten Datei und wird
hier eingebunden:

@project-identifier.md

## Typ-Codes

| Code | Bedeutung |
|------|-----------|
| `AUD` | Audit |
| `RPT` | Report / Analyse |
| `RFC` | Konzept / Framework-Entwurf |
| `BT` | Backtesting-Plan oder -Report |
| `ADR` | Architectural Decision Record — nicht-offensichtliche Entscheidung mit Trade-off |

**Nicht mehr als doc-ids:** `FIX`, `FIXR`, `TODO` — diese werden als Tickets erfasst (`tickets/open/`). Zusammengehörige Tasks via `group:`-Feld gruppieren.

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
Liegt im Repo-Root (oder im jeweiligen Kontext-Ordner bei Multi-Context-Repos).

## Ablage

Dokumente liegen im projektspezifischen Ordner — keine zentrale Registry.

```
docs/
├── {YYYYMMDD}-{SEQ}_{Beschreibung}/
│   └── {TYPE}-{YYYYMMDD}-{SEQ}_{Beschreibung}.md
└── archiv/
```
