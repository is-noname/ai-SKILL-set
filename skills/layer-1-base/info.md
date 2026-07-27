# Layer 1: Base Skills

**Zweck:** Direkt nutzbare Basis-Skills. Werden vom User oder Agent aufgerufen und können Layer-0-Primitives als Dependency nutzen.

**Abhängigkeiten:** Layer 0 (Core) muss vorhanden sein.

**Verfügbare Skills:**

| Skill | Beschreibung | Dependencies |
|-------|-------------|-------------|
| `decision-sheet` | Viele Entscheidungsfragen gebündelt ausserhalb der CLI beantworten (JSONL-Sheet + HTML-Renderer) | — |
| `grill-me` | Plan/Design-Review via relentless interview | `grilling` |
| `izg-ai-repo-pull` | Skills aus dem ai-SKILL-set repo in ein Projekt pullen | — |
| `izg-domain-modeling` | Domänenmodell aufbauen — Begriffe, ADRs (doc-ids), CONTEXT.md | — |
| `izg-starter-icon-mkr` | Desktop-Startericon für lokale Server-Apps (Linux Mint/Cinnamon) | — |

**Hinweis:** Skills hier sollten projekt-unabhängig und wiederverwendbar sein.
