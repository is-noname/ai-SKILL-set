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
│   ├── pull_skill.py                # Backend für den izg-ai-repo-pull Skill
│   ├── init_tickets.sh              # Ticketsystem in einem Projekt bootstrappen
│   ├── next_ticket_id.sh            # Nächste Ticket-ID (selbstheilend, mit Lock)
│   └── setup_global_conventions.sh      # Konventionsdocs global pro Agent deployen
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

## Externe Voraussetzungen (`requires.json`)

Braucht ein Skill etwas, das **nicht** im Repo liegt — ein Kommando, eine
Umgebungsvariable, ein Python-Paket, eine Datei — gehört das in eine
`requires.json` neben die `SKILL.md`. Prosa im SKILL.md reicht nicht: sie wird
überlesen, und der Fehler fällt erst mitten in einer Session auf.

```json
{
  "requires": [
    { "type": "cmd", "value": "xdg-open",
      "hint": "Paket 'xdg-utils' installieren" },
    { "type": "env", "value": "AGENTMAIL_API_KEY",
      "hint": "Key von agentmail.to in die Skill-eigene .env eintragen" },
    { "type": "py", "value": "requests", "hint": "pip install requests" },
    { "type": "file", "value": "~/.config/foo/config.toml",
      "optional": true, "hint": "Ohne Config nutzt der Skill Defaults" }
  ]
}
```

| Feld | Pflicht | Bedeutung |
|------|---------|-----------|
| `type` | ja | `cmd` (in `PATH`), `env` (Shell **oder** skill-eigene `.env`), `py` (importierbar), `file` (Pfad existiert, `~`/`$VAR` werden aufgelöst) |
| `value` | ja | Name des Kommandos / der Variable / des Moduls bzw. der Pfad |
| `hint` | nein, aber praktisch immer sinnvoll | **Wie man es behebt** — dieser Text ist das, was der Nutzer zu sehen bekommt |
| `optional` | nein (Default `false`) | `true` = Skill läuft eingeschränkt weiter (graceful degradation), wird als `~` gemeldet statt als `✗` |

**Regel für `optional`:** Bricht der Skill ohne die Voraussetzung ab → Pflicht.
Läuft er mit reduziertem Komfort weiter → `optional: true`.

### `setup.sh` (optional)

Lässt sich eine Voraussetzung automatisch herstellen (`.env` aus Vorlage anlegen,
Paket installieren), gehört ein ausführbares `setup.sh` neben die `SKILL.md`. Es
wird **nie ungefragt** ausgeführt — nur bei `--setup`:

```bash
python3 scripts/pull_skill.py pull agentmail --target .claude/skills --setup
```

Konventionen fürs Script: idempotent (mehrfacher Lauf schadet nicht), überschreibt
nie eine bestehende `.env`, und beendet sich mit Exit-Code ≠ 0, wenn noch etwas
von Hand nachzutragen ist.

### Prüfung

- `pull` und `update` prüfen automatisch nach dem Kopieren und melden Fehlendes
  mit `hint`.
- `python3 scripts/pull_skill.py doctor --target .claude/skills` prüft alle
  installierten Skills nachträglich — für den Fall, dass eine Voraussetzung
  später wegbricht (Key rotiert, Paket deinstalliert). Exit-Code 1 bei fehlender
  Pflicht-Voraussetzung.
- `generate_registry.py` inlined `requires` in `registry.json` (sichtbar **vor**
  dem Pull) und lässt den Pre-Commit-Hook bei kaputter `requires.json` scheitern.

**Secrets:** Eine `.env` im Skill-Verzeichnis gehört zur Maschine, nicht zum
Skill — sie wird weder gepullt noch beim Update-Vergleich berücksichtigt.

Hintergrund und verworfene Alternativen: `docs/.../ADR-20260816-001`.

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

> Maßgebliche Quelle ist `registry.json` bzw. `python3 scripts/pull_skill.py list`.
> Diese Tabelle ist nur eine Momentaufnahme und kann driften.

| Skill | Layer | Beschreibung | Deps |
|-------|-------|-------------|------|
| `grilling` | 0 | Relentless interview prompt (Primitive) | — |
| `handoff` | 0 | Konversation in ein Handoff-Dokument für einen anderen Agent komprimieren | — |
| `izg-create-fixplan` | 0 | Umsetzbaren Fix-Plan erstellen | — |
| `grill-me` | 1 | Plan/Design-Review via Interview | `grilling` |
| `izg-ai-repo-pull` | 1 | Skills aus diesem Repo in ein Projekt pullen | — |
| `izg-ai-repo-pull-update` | 1 | Bereits installierte Skills im Projekt aktualisieren | — |
| `izg-domain-modeling` | 1 | Domänenmodell aufbauen — Begriffe, ADRs, CONTEXT.md | — |
| `izg-starter-icon-mkr` | 1 | Desktop-Startericon für lokale Server-Apps | — |
| `prototype` | 1 | Wegwerf-Prototyp zum Ausarbeiten eines Designs | — |
| `teach` | 1 | Nutzer ein Konzept/Skill im Workspace beibringen | — |
| `grill-with-docs` | 2 | Review + ADR/Glossar-Erstellung in einer Session | `grilling`, `izg-domain-modeling` |
| `improve-codebase-architecture` | 3 | Codebase auf Vertiefungs-Chancen scannen, visuell aufbereiten | — |

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
- Pre-commit Hook (`hooks/repo-local/pre-commit-registry.sh`) — regeneriert `registry.json` bei SKILL.md-Änderungen

**Offen:**
- `izg-ai-repo-update` Skill
- `izg-ai-repo-search` Skill
- `projects/` vs `layer-4-project/` Abgrenzung klären (IZG-T-002)
- Update-Workflow: wie werden bereits gepullte Skills in Projekten aktualisiert?
