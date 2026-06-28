# Setup: ticket-system

Leichtgewichtiges, file-basiertes Ticket-Tracking pro Projekt. Dieses Verzeichnis ist
**kein Code** — es ist das **Manifest** eines repo-übergreifenden Subsystems, dessen
Bestandteile über `docs/`, `hooks/`, `scripts/` und `skills/` verteilt liegen.

Ein Agent, der hierherkommt, findet in `manifest.json` **alle** Komponenten ohne suchen
zu müssen.

## Warum ein Manifest statt eines Layers?

Das Ticketsystem ist kein einzelner Skill — es besteht aus Hook + Konvention + Scripts +
Deploy-Logik + Agent-Config-Patches. Die Layer-Achse (0–4) klassifiziert *einzelne Skills*
nach Wiederverwendbarkeit und passt für ein verstreutes Subsystem nicht. `set setups/` ist
die orthogonale Achse: „welche Teile gehören zu *einem* Feature".

## Abhängigkeit

`ticket-system` hängt an **`project-identifier`** — der geteilten Prefix-Registry
(`docs/project-identifier.md`). Die Ticket-ID `{PRJ}-T-{NNN}` braucht das Projekt-Prefix
`{PRJ}`, das dort gepflegt wird.

Wichtig: Das ist **nicht** dasselbe wie eine Abhängigkeit auf `doc-ids`. Die Prefix-Registry
ist seit dem Split eine eigenständige, geteilte Datei — `doc-ids` und `ticket-system` nutzen
sie beide und sind dadurch **Geschwister**, nicht voneinander abhängig:

```
project-identifier  (Prefix-Registry, shared user-state)
        ↑                 ↑
   doc-ids          ticket-system
```

`tickets.md` verweist deshalb direkt auf `project-identifier.md` (statt den Umweg über
`doc-ids.md`). `doc-ids.md` und `project-identifier.md` selbst gehören in eigene Setups
(`set setups/doc-ids/`, `set setups/project-identifier/` — noch anzulegen).

## Bootstrap

```bash
bash scripts/init_tickets.sh /pfad/zum/projekt
```

Danach `@tickets.md` und `@doc-ids.md` in der `CLAUDE.md` des Projekts verlinken.

## Pflege

Das Manifest wird derzeit **statisch** gepflegt — bei Änderungen an Komponenten hier
nachziehen. Falls es sich bewährt, kann ein `scripts/generate_setups.py` es analog zu
`generate_registry.py` aus Markern generieren (dann driftet es nicht).
