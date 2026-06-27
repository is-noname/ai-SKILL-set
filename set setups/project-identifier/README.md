# Setup: project-identifier

Die geteilte **Kürzel-Registry**: ordnet jedem Projekt ein kurzes `{PRJ}`-Kürzel zu
(`IZG` → ai-SKILL-set, `STK` → Stonky_v1, …). Einzige Quelle der Wahrheit für `{PRJ}`.

## Rolle im Setup-DAG

Dies ist das **Leaf** — es hängt an nichts und wird von zwei anderen Setups konsumiert:

```
project-identifier  ← dieses Setup
        ↑                 ↑
   doc-ids          ticket-system
```

- `doc-ids` braucht `{PRJ}` für IDs wie `AUD-20260301-001`.
- `ticket-system` braucht `{PRJ}` für IDs wie `IZG-T-001`.

## User-State, nicht Konvention

`docs/project-identifier.md` ist **kein** Konventionsdokument, sondern gepflegter
User-State. `setup_global_conventions.sh` legt es nur an, wenn es fehlt — eine vorhandene Registry
wird **nie** überschrieben, damit lokal eingetragene Kürzel erhalten bleiben. Deshalb ist
es bewusst aus `doc-ids.md` ausgelagert (das als reine Konvention bei jedem Update neu
geschrieben wird).
