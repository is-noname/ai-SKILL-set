# ai-SKILL-set

> Modulares Skill-Repository für gezielte Nutzung in verschiedenen Projekten

---

## Zweck

Zentrales Repository für Claude Code Skills. Skills werden **nicht global installiert**, sondern pro Projekt selektiv gepullt. So hat jedes Projekt nur die Skills die es braucht — kein Overhead, kein Rauschen.

**Workflow:**
1. Skills im Repo pflegen und weiterentwickeln
2. Bei neuem Projekt: `/pull-skills` aufrufen, Profil wählen, fertig
3. Skills landen in `.claude/skills/` des jeweiligen Projekts

---

## Struktur

```
ai-SKILL-set/
├── registry.json                    # Auto-generierter Index (via pre-commit hook, Phase 2)
├── sets/                            # Vorgefertigte Skill-Kombinationen (JSON)
│   └── grilling.json
├── layer-0-core/                    # Skill-Primitives (nur als Dependency, nie direkt aufgerufen)
│   └── {skill-name}/
│       └── SKILL.md
├── layer-1-base/                    # Direkt nutzbare Basis-Skills
│   └── {skill-name}/
│       └── SKILL.md
├── layer-2-domain/                  # Domänen-spezifische Skills
│   ├── finance/
│   ├── coding/
│   └── analysis/
├── layer-3-project/                 # Projekt-spezifische Skills
│   └── {project-name}/
│       └── {skill-name}/
└── projects/                        # Projekt-Profile (welche Skills gehören zusammen)
    └── {project-name}/
        ├── skills.json
        └── config.json
```

---

## Layer-Übersicht

| Layer | Name | Semantik | Beispiel |
|-------|------|----------|---------|
| **0** | Core | Skill-Primitives — nur als Dependency, nie direkt aufgerufen | `grilling` |
| **1** | Base | Direkt nutzbare Basis-Skills, können Layer 0 nutzen | `grill-me` |
| **2** | Domain | Spezialisierte Skills für bestimmte Fachbereiche | Finance, Coding |
| **3** | Project | Projekt-spezifische Anpassungen, nicht wiederverwendbar | Custom Logic |

**Dependency-Regel:** Ein Skill aus Layer N darf nur Skills aus Layer 0 bis N-1 als Dependency haben.

**Layer-0-Regel:** Layer-0-Skills dürfen nicht direkt in `sets/` oder `projects/skills.json` stehen — sie werden immer transitiv geladen.

---

## SKILL.md Format

Minimales YAML Frontmatter, 4 Pflichtfelder:

```yaml
---
name: grill-me
description: A relentless interview to sharpen a plan or design.
layer: 1
dependencies: ["grilling"]
---

Skill-Inhalt hier...
```

---

## Sets

Sets sind JSON-Listen vorgefertigter Skill-Kombinationen. Kein eigener Ordner-Layer — nur Konfigurationsdateien.

```json
{
  "name": "grilling",
  "description": "Skills für Plan- und Design-Reviews",
  "skills": ["grill-me"]
}
```

Beim Pull eines Sets werden alle gelisteten Skills + ihre transitiven Dependencies geladen.

---

## Projekt-Profile

Jedes Projekt hat ein Profil in `projects/{name}/skills.json`:

```json
{
  "skills": ["grill-me", "domain-modeling"],
  "sets": ["grilling"]
}
```

Der `/pull-skills` Skill scannt `projects/` dynamisch und zeigt eine Auswahlliste.

---

## Dependency-Auflösung

Der pull-skill löst Abhängigkeiten automatisch rekursiv auf:

```
Set: grilling
  → grill-me (Layer 1)
      → grilling (Layer 0, auto)
```

Alle Skills landen parallel in `.claude/skills/` des Projekts.

---

## Verfügbare Skills

| Skill | Layer | Beschreibung |
|-------|-------|-------------|
| `grilling` | 0 | Relentless interview prompt (Primitive) |
| `grill-me` | 1 | Plan/Design-Review via Interview |
| `grill-with-docs` | 1 | Review + ADR/Glossar-Erstellung (benötigt `domain-modeling`) |
| `izg-starter-icon-mkr` | 1 | Desktop-Startericon für lokale Server-Apps (Linux Mint/Cinnamon) |

---

## Status

**Fertig:**
- Layer-Struktur (0-3) mit klarer Semantik
- SKILL.md Format (4 Pflichtfelder, YAML Frontmatter)
- Sets-Konzept (JSON-Konfigurationen in `sets/`)
- Projekt-Profile in `projects/`
- Dependency-Regel + Layer-0-Validierung (durch registry-Generator)
- Versioning via Git Branches

**Phase 2 (nach Grundgerüst):**
- Pull-Skill Implementation (global in `~/.claude/skills/`)
- registry.json Generierungs-Script
- Pre-commit Hook für automatische registry-Generierung
- Update-Skills Workflow

Detaillierte offene Punkte: [OPEN-ITEMS.md](OPEN-ITEMS.md)
