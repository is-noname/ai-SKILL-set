---
name: izg-ai-repo-global-update
description: Checks and updates the global agent conventions (tickets.md, doc-ids.md, init_tickets.sh, ticket-mover hook) deployed in agent dirs (~/.claude etc.) against the ai-SKILL-set repo. Use when the user wants to update, refresh, sync, or drift-check their global conventions/tickets/doc-ids setup.
layer: 1
dependencies: []
disable-model-invocation: true
---

# IZG AI Repo — Global Conventions Update

Aktualisiert die **global** deployten Konventionen/Artefakte eines AI-Agenten gegen das
Repo — das Pendant zu `izg-ai-repo-pull-update`, nur für `~/.claude`, `~/.codex`,
`~/.gemini`, `~/.vibe` statt für Projekt-Skills.

> **Architektur:** Dünner Wrapper um zwei zentrale Skripte im Repo (`scripts/`, **nicht**
> im Skill): `check_global_drift.sh` (read-only Drift-Check) und `setup_global.sh`
> (idempotenter Re-Deploy). Setzt voraus, dass das Repo unter `REPO` existiert. Managed:
> `tickets.md`, `doc-ids.md`, `scripts/init_tickets.sh`, `hooks/ticket-mover.sh`.
> `project-identifier.md` (User-State / Kürzel-Registry) wird **nie** angefasst.

## Ablauf

```bash
REPO=~/Dokumente/AI/ai-SKILL-set

# 1. Drift prüfen (read-only) — alle bekannten Agent-Dirs unter $HOME
bash $REPO/scripts/check_global_drift.sh

# ... oder gezielt ein Agent-Dir
bash $REPO/scripts/check_global_drift.sh ~/.claude

# 2. Re-Deploy (idempotent) — gezielt, mehrere, oder alle
bash $REPO/scripts/setup_global.sh ~/.claude          # ein Dir
bash $REPO/scripts/setup_global.sh ~/.claude ~/.codex # mehrere
bash $REPO/scripts/setup_global.sh --all              # alle bekannten Agent-Dirs
```

## Ohne Argumente aufgerufen

1. Drift-Check über alle Agent-Dirs laufen lassen
2. Ausgabe zeigen (ok / drift / missing pro Datei)
3. Ist alles aktuell → melden und fertig
4. Gibt es Drift → fragen, welche Agent-Dirs re-deployt werden sollen
5. Für die gewählten Dirs `setup_global.sh <dir>` ausführen

## Nach dem Update

Kurz melden:
- Re-deployt (welche Agent-Dirs)
- Was war veraltet/fehlte
- Alles aktuell (wenn nichts zu tun war)

`project-identifier.md` bleibt unangetastet — nie als „nicht aktualisiert" flaggen.
Nicht weiter erklären.
