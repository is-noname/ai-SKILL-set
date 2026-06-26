# ai-SKILL-set

> Modulares Skill-Repository für gezielte Nutzung in verschiedenen Projekten

---

## Zweck

Zentrales Repository für Claude Code Skills. Skills werden **nicht global installiert**, sondern pro Projekt selektiv gepullt. So hat jedes Projekt nur die Skills die es braucht — kein Overhead, kein Rauschen.

**Workflow:**
1. Skills im Repo pflegen und weiterentwickeln
2. Bei neuem Projekt: `/izg-ai-repo-pull` aufrufen, Skills oder Set angeben
3. Skills landen in `.claude/skills/` des jeweiligen Projekts

---

## Struktur

```
ai-SKILL-set/
├── registry.json                    # Auto-generierter Index (scripts/generate_registry.py)
├── scripts/
│   ├── generate_registry.py         # Scannt SKILL.md, validiert, schreibt registry.json
│   └── pull_skill.py                # Backend für den izg-ai-repo-pull Skill
├── skills/
│   ├── layer-0-core/                # Skill-Primitives (nur als Dependency, nie direkt aufgerufen)
│   ├── layer-1-base/                # Direkt nutzbare Basis-Skills
│   ├── layer-2-main/                # Kompositionen aus layer-0/1 Skills
│   ├── layer-3-domain/              # Domänen-spezifische Skills
│   │   ├── finance/
│   │   ├── coding/
│   │   └── analysis/
│   ├── layer-4-project/             # Projekt-spezifische Skills (nicht wiederverwendbar)
│   ├── sets/                        # Vorgefertigte Skill-Kombinationen (JSON)
│   └── projects/                    # Projekt-Profile mit skills.json
```

---

## Layer-Übersicht

| Layer | Name | Semantik | Beispiel |
|-------|------|----------|---------|
| **0** | Core | Primitives — nur als Dependency, nie direkt aufgerufen | `grilling` |
| **1** | Base | Direkt nutzbare Einzelskills | `grill-me`, `izg-ai-repo-pull` |
| **2** | Main | Kompositionen aus Layer-0/1 Skills | `grill-with-docs` |
| **3** | Domain | Domänen-spezifisch (finance, coding, analysis) | — |
| **4** | Project | Projekt-spezifisch, nicht wiederverwendbar | `stonky-report-writer` |

**Dependency-Regeln:**
- Layer 0 hat keine Deps
- Aufwärts-Dependencies (dep.layer > skill.layer) sind verboten
- Zyklische Dependencies sind verboten
- Layer-0-Skills stehen nie direkt in `sets/` oder `projects/skills.json` — sie werden transitiv geladen

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

**Dateiname:** Genau `SKILL.md` (Großschreibung). Linux ist case-sensitiv —
`skill.md` o.ä. wird vom Generator zwar erfasst, aber als Warnung gemeldet.
Generierte/lokale Artefakte (`__pycache__/`, `*.pyc`, `*.backup`, `*.db`) gehören
nicht ins Skill-Verzeichnis und werden ignoriert (`.gitignore`, Update-Vergleich).

---

## `projects/` vs `layer-4-project/` — klare Abgrenzung

| Verzeichnis | Enthält | Enthält NICHT |
|------------|---------|---------------|
| `projects/{name}/` | `skills.json`, `config.json` — **Profil**: welche Skills ein Projekt braucht | SKILL.md-Dateien |
| `layer-4-project/{name}/` | SKILL.md-Dateien — **Implementierung**: projekt-spezifische Skills | Profile oder JSON-Config |

**Regel:** `projects/` ist reine Konfiguration (Pull-Profile). Jede SKILL.md die nicht Layer 0–3 taugt gehört nach `layer-4-project/`.

**Entscheidungsbaum für neue Stonky-Skills:**
1. Ist der Skill in anderen Projekten wiederverwendbar? → Layer 3-Domain (`layer-3-domain/finance/`)
2. Stonky-spezifisch (Template, Reportformat, eigene Logik)? → `layer-4-project/Stonky/`
3. Nur Konfiguration (welche Skills pullen)? → `projects/Stonky/skills.json`

---

## Sets

Sets sind JSON-Listen vorgefertigter Skill-Kombinationen:

```json
{
  "name": "grilling",
  "description": "Skills für Plan- und Design-Reviews",
  "skills": ["grill-me"]
}
```

---

## Dependency-Auflösung

`pull_skill.py` löst Abhängigkeiten transitiv auf, sortiert topologisch (Deps zuerst):

```
pull grill-with-docs
  → grilling (layer 0, auto)
  → izg-domain-modeling (layer 1, auto)
  → grill-with-docs (layer 2)
```

---

## Verfügbare Skills

| Skill | Layer | Beschreibung |
|-------|-------|-------------|
| `grilling` | 0 | Relentless interview prompt (Primitive) |
| `grill-me` | 1 | Plan/Design-Review via Interview |
| `izg-ai-repo-pull` | 1 | Skills aus diesem Repo in ein Projekt pullen |
| `izg-domain-modeling` | 1 | Domänenmodell aufbauen — Begriffe, ADRs, CONTEXT.md |
| `izg-starter-icon-mkr` | 1 | Desktop-Startericon für lokale Server-Apps |
| `grill-with-docs` | 2 | Review + ADR/Glossar-Erstellung in einer Session |

---

## Status

**Fertig:**
- Layer-Struktur (0–4) mit klarer Semantik
- SKILL.md Format (4 Pflichtfelder, YAML Frontmatter)
- `scripts/generate_registry.py` — scannt, validiert, schreibt `registry.json`
- `scripts/pull_skill.py` — Dependency-Auflösung + Copy, `pull`/`list`, `--set`, `--force`, `--dry-run`
- `izg-ai-repo-pull` Skill
- Sets-Konzept (`sets/`)
- Projekt-Profile (`projects/`)
- Pre-commit Hook (`hooks/pre-commit-registry.sh`) — regeneriert `registry.json` bei SKILL.md-Änderungen

**Offen:**
- `izg-ai-repo-update` Skill
- `izg-ai-repo-search` Skill
- `projects/` vs `layer-4-project/` Abgrenzung klären (IZG-T-002)
- Update-Workflow: wie werden bereits gepullte Skills in Projekten aktualisiert?
