---
name: izg-domain-modeling
description: Baut das Domänenmodell eines Projekts auf — Begriffe klären, ADRs erstellen, Glossar pflegen. Verwendet doc-ids für ADR-Benennung. Ersetzt domain-modeling vollständig.
layer: 1
dependencies: []
disable-model-invocation: true
---

# IZG Domain Modeling

Aktive Disziplin: Begriffe herausfordern, Randfall-Szenarien erfinden, Glossar und Entscheidungen sofort festhalten wenn sie kristallisieren.

## Dateistruktur

```
/
├── CONTEXT.md          ← lebendes Glossar (kein Datum, kein SEQ)
└── workspace/
    └── {PROJ}-ADR-{YYYYMMDD}-{SEQ}_{Beschreibung}.md
```

Bei mehreren Kontexten: `CONTEXT-MAP.md` im Root, je ein `CONTEXT.md` pro Kontext-Ordner.

Dateien lazy anlegen — nur wenn es etwas zu schreiben gibt.

## Verhalten während der Session

**Glossar challengen** — wenn der User einen Begriff nutzt der mit `CONTEXT.md` kollidiert, sofort ansprechen: „Dein Glossar definiert X als Y, du meinst aber Z — was gilt?"

**Sprache schärfen** — vage oder überladene Begriffe präzisieren: „Du sagst ‚Account' — meinst du den Customer oder den User?"

**Konkrete Szenarien** — Beziehungen mit Randfall-Szenarien stress-testen, um Grenzen zwischen Konzepten zu klären.

**Code gegenprüfen** — wenn der User beschreibt wie etwas funktioniert, prüfen ob der Code übereinstimmt. Widersprüche benennen.

**CONTEXT.md sofort aktualisieren** — nicht aufsparen, Begriffe festhalten sobald sie geklärt sind.

## CONTEXT.md Format

```md
# {Context Name}

{Ein bis zwei Sätze: was dieser Kontext ist und warum er existiert.}

## Language

**{Begriff}**:
{Ein bis zwei Sätze: was der Begriff IST, nicht was er tut.}
_Avoid_: {Synonyme die im Projekt nicht verwendet werden sollen}
```

Regeln:
- `_Avoid:` für jeden Begriff — explizit ausschließen was er nicht ist
- Nur projektspezifische Konzepte, keine allgemeinen Programmierkonzepte
- Kein Implementierungsdetail, kein Spec, kein Scratch-Pad — nur Glossar

## ADR erstellen

Nur wenn alle drei zutreffen:
1. Schwer rückgängig zu machen
2. Ohne Kontext überraschend
3. Echtes Trade-off gegen konkrete Alternativen

**Benennung** nach `@doc-ids.md` (Typ `ADR`):
```
{PROJ}-ADR-{YYYYMMDD}-{SEQ}_{Beschreibung}.md
```

**Inhalt** (minimal):
```md
# {Kurztitel der Entscheidung}

{1–3 Sätze: Kontext, Entscheidung, Begründung.}
```

Optionale Abschnitte nur wenn sie echten Mehrwert liefern:
- **Status** (`proposed | accepted | deprecated | superseded by {PROJ}-ADR-…`)
- **Verworfene Alternativen** — wenn die Ablehnung nicht offensichtlich ist
- **Konsequenzen** — wenn nicht-offensichtliche Folgeeffekte bestehen
