# Setup: doc-ids

Namenskonvention für Dokument-IDs: `{TYPE}-{YYYYMMDD}-{SEQ}_{Beschreibung}.md` mit
Typ-Codes (`AUD`, `RPT`, `RFC`, `BT`, `ADR`) und ADR-Eingangsfilter.

## Abhängigkeit

`doc-ids` hängt an **`project-identifier`** — IDs werden projektbezogen über `{PRJ}`
vergeben, und `doc-ids.md` bindet die Kürzel-Registry per `@project-identifier.md` ein.

```
project-identifier
        ↑
   doc-ids          ← dieses Setup
```

`doc-ids` und `ticket-system` sind **Geschwister** (beide hängen an `project-identifier`),
nicht voneinander abhängig.

## Konvention vs. State

`docs/doc-ids.md` ist **reine Konvention** und wird bei jedem `setup_global.sh`-Lauf neu
geschrieben. Der einzige veränderliche Teil — die Kürzel — ist bewusst in das separate
Setup `project-identifier` ausgelagert, damit Updates es nie überschreiben.
