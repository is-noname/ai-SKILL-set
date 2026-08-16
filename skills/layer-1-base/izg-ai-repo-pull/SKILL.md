---
name: izg-ai-repo-pull
description: Pulls skills from the izg ai-SKILL-set repo into the current project. Resolves transitive dependencies automatically. Use when the user wants to install, add, or pull a skill into a project.
layer: 1
dependencies: []
disable-model-invocation: true
---

# IZG AI Repo — Pull

Installiert Skills aus `~/Dokumente/AI/ai-SKILL-set` in das aktuelle Projekt (`.claude/skills/`).

> **Architektur:** Dieser Skill ist ein dünner Wrapper. Die Engine `pull_skill.py` liegt
> zentral im Repo (`scripts/`), **nicht** im Skill — sie braucht `registry.json` und den
> `skills/`-Baum, die nur dort existieren. Fehlt das Repo unter dem unten gesetzten
> `REPO`-Pfad, wird es automatisch geklont. Voraussetzung: `python3` + `git`.

## Ablauf

**Ohne Argumente aufgerufen:** Liste ausgeben und fragen was gepullt werden soll.

**Mit Skill-Namen oder Set:** direkt pullen.

```bash
REPO=~/Dokumente/AI/ai-SKILL-set

# Repo nicht vorhanden? Einmalig clonen
if [ ! -d "$REPO" ]; then
  git clone https://github.com/is-noname/ai-SKILL-set.git "$REPO"
fi

# Liste anzeigen (ohne Argumente)
python3 $REPO/scripts/pull_skill.py list

# Einzelne Skills
python3 $REPO/scripts/pull_skill.py pull grill-me --target .claude/skills

# Skill-Set
python3 $REPO/scripts/pull_skill.py pull --set grilling --target .claude/skills

# Vorschau ohne Kopieren
python3 $REPO/scripts/pull_skill.py pull grill-me --dry-run

# Überschreiben (nach Update)
python3 $REPO/scripts/pull_skill.py pull grill-me --force

# Fehlende externe Voraussetzungen automatisch einrichten (führt setup.sh aus)
python3 $REPO/scripts/pull_skill.py pull agentmail --target .claude/skills --setup

# Installierte Skills nachträglich auf externe Voraussetzungen prüfen
python3 $REPO/scripts/pull_skill.py doctor --target .claude/skills
```

## Ohne Argumente

1. `pull_skill.py list` ausführen
2. Ausgabe dem Nutzer zeigen
3. Fragen: welche Skills oder welches Set soll installiert werden?
4. Dann pullen

## Nach der Installation

Kurz melden:
- Installiert (inkl. auto-gezogene Deps)
- Übersprungen (bereits vorhanden)

Nicht weiter erklären — der Nutzer kennt das System.

**Ausnahme:** Meldet der Pull fehlende externe Voraussetzungen (`✗`-Zeilen), diese
wörtlich weitergeben — der Skill ist sonst unbrauchbar. Gibt es dazu ein `setup.sh`,
anbieten, den Pull mit `--setup` zu wiederholen. `~`-Zeilen sind optional und nur
erwähnenswert, wenn sie den geplanten Einsatz betreffen.
