# Layer 0: Core Skills (Primitives)

**Zweck:** Skill-Primitives — werden von anderen Skills als Dependency genutzt, nie direkt vom User oder Agent aufgerufen.

**Semantik:** Ein Layer-0-Skill darf nicht direkt in `sets/` oder `projects/*/skills.json` stehen. Er wird immer transitiv via Dependency-Auflösung geladen.

**Abhängigkeiten:** Keine (Layer 0 hat keine Inbound-Dependencies auf andere Skills).

**Verfügbare Skills:**

| Skill | Beschreibung | Genutzt von |
|-------|-------------|-------------|
| `grilling` | Relentless interview prompt für Plan/Design-Reviews | `grill-me`, `grill-with-docs` |

**Hinweis:** Neue Skills hier einordnen wenn sie ausschließlich als Dependency anderer Skills existieren und nie eigenständig aufgerufen werden.
