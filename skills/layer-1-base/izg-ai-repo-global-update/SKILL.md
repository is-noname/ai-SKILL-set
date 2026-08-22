---
name: izg-ai-repo-global-update
description: Checks and updates the global agent conventions (tickets.md, doc-ids.md, design-tokens.md, init_tickets.sh, ticket-mover hook) deployed in agent dirs (~/.claude etc.) and the per-project ticket infrastructure (scripts/tickets.sh, PROTOCOL.md, .counter) against the ai-SKILL-set repo. Use when the user wants to update, refresh, sync, or drift-check their global conventions/tickets/doc-ids setup or their projects' ticket setup.
layer: 1
dependencies: []
disable-model-invocation: true
---

# IZG AI Repo — Global Conventions Update

Aktualisiert die **global** deployten Konventionen/Artefakte eines AI-Agenten gegen das
Repo — das Pendant zu `izg-ai-repo-pull-update`, nur für `~/.claude`, `~/.codex`,
`~/.gemini`, `~/.vibe` statt für Projekt-Skills.

> **Architektur:** Dünner Wrapper um zwei zentrale Skripte im Repo (`scripts/`, **nicht**
> im Skill): `check_global_drift.sh` (read-only Drift-Check) und `setup_global_conventions.sh`
> (idempotenter Re-Deploy). Setzt voraus, dass das Repo unter `REPO` existiert. Managed:
> `tickets.md`, `doc-ids.md`, `design-tokens.md`, `scripts/init_tickets.sh`, `hooks/global/ticket-mover.sh`.
> `project-identifier.md` (User-State / Prefix-Registry) wird **nie** angefasst.
>
> Dazu die **Projekt-Ebene** (IZG-T-158): `check_project_drift.sh` (read-only) und
> `init_tickets.sh` (idempotenter Re-Deploy) fuer `scripts/tickets.sh`,
> `scripts/next_ticket_id.sh`, die `tickets/`-Statusordner, den Prefix in
> `tickets/PROTOCOL.md` und `.counter`.

## Ablauf

```bash
REPO=~/Dokumente/AI/ai-SKILL-set

# 1. Drift prüfen (read-only) — alle bekannten Agent-Dirs unter $HOME
bash $REPO/scripts/check_global_drift.sh

# ... oder gezielt ein Agent-Dir
bash $REPO/scripts/check_global_drift.sh ~/.claude

# 2. Re-Deploy (idempotent) — gezielt, mehrere, oder alle
bash $REPO/scripts/setup_global_conventions.sh ~/.claude          # ein Dir
bash $REPO/scripts/setup_global_conventions.sh ~/.claude ~/.codex # mehrere
bash $REPO/scripts/setup_global_conventions.sh --all              # alle bekannten Agent-Dirs
```

### Projekt-Ebene (Ticket-Infrastruktur)

```bash
# 1. Drift prüfen (read-only) — alle Projekte mit tickets/-Ordner unter ~/Dokumente
bash $REPO/scripts/check_project_drift.sh

# ... oder gezielt ein Projekt
bash $REPO/scripts/check_project_drift.sh /pfad/zum/projekt

# 2. Nachziehen (idempotent) — PREFIX nur nötig, wenn PROTOCOL.md noch {PRJ} enthält
bash $REPO/scripts/init_tickets.sh /pfad/zum/projekt [PREFIX]

# 3. Counter heilen, falls der Bericht Drift meldet
bash /pfad/zum/projekt/scripts/tickets.sh next PREFIX --repair
```

Nie ungefragt über alle Projekte re-deployen — den Bericht zeigen, dann fragen,
welche Projekte nachgezogen werden sollen.

## Ohne Argumente aufgerufen

1. Beide Drift-Checks laufen lassen (`check_global_drift.sh`, `check_project_drift.sh`)
2. Ausgabe zeigen (ok / drift / missing pro Datei bzw. pro Projekt)
3. Ist alles aktuell → melden und fertig
4. Gibt es Drift → fragen, welche Agent-Dirs bzw. Projekte nachgezogen werden sollen
5. Für die gewählten Ziele `setup_global_conventions.sh <dir>` bzw.
   `init_tickets.sh <projekt> [PREFIX]` ausführen

## Nach dem Update

Kurz melden:
- Re-deployt (welche Agent-Dirs / Projekte)
- Was war veraltet/fehlte
- Alles aktuell (wenn nichts zu tun war)

`project-identifier.md` bleibt unangetastet — nie als „nicht aktualisiert" flaggen.
Nicht weiter erklären.
