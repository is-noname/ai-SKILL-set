# Layer 1: Base Skills

**Zweck:** Direkt nutzbare Basis-Skills. Werden vom User oder Agent aufgerufen und können Layer-0-Primitives als Dependency nutzen.

**Abhängigkeiten:** Layer 0 (Core) muss vorhanden sein.

**Verfügbare Skills:**

| Skill | Beschreibung | Dependencies |
|-------|-------------|-------------|
| `grill-me` | Plan/Design-Review via relentless interview | `grilling` |
| `grill-with-docs` | Review + ADR/Glossar-Erstellung | `grilling`, `izg-domain-modeling` |
| `izg-starter-icon-mkr` | Desktop-Startericon für lokale Server-Apps (Linux Mint/Cinnamon) | — |

**Hinweis:** Skills hier sollten projekt-unabhängig und wiederverwendbar sein.
