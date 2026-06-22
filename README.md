# izg-ai-skill-set

Modulares Skill-Repository für Claude Code. Skills werden pro Projekt selektiv gepullt — kein globaler Overhead.

## Schnellstart

```bash
# In einem neuen Projekt:
/izg-ai-repo-pull
```

Zeigt verfügbare Skills, du wählst was du brauchst. Dependencies werden automatisch aufgelöst.

## Inhalt

- **`skills/`** — Skills nach Layer (0=Primitives, 1=Base, 2=Main, 3=Domain, 4=Project)
- **`scripts/`** — `generate_registry.py`, `pull_skill.py`
- **`hooks/`** — Pre-commit Hook für automatische registry-Regenerierung
- **`commands/`** — Slash Commands
- **`agents/`** — Spezialisierte Agenten

Details: [skills/README.md](skills/README.md)
