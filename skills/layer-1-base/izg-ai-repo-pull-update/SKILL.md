---
name: izg-ai-repo-pull-update
description: Updates already-installed skills in the current project to the latest version from the ai-SKILL-set repo. Use when the user wants to update, refresh, or sync installed skills.
layer: 1
dependencies: []
disable-model-invocation: true
---

# IZG AI Repo — Update

Vergleicht installierte Skills mit der Repo-Version und aktualisiert veraltete.

> **Architektur:** Dünner Wrapper um die zentrale Engine `pull_skill.py` (`scripts/` im
> Repo, **nicht** im Skill — sie braucht `registry.json` und den `skills/`-Baum). Setzt
> voraus, dass das Repo unter `REPO` existiert; fehlt es, zuerst via `izg-ai-repo-pull`
> bootstrappen (der klont es bei Bedarf). Voraussetzung: `python3`.

## Ablauf

```bash
REPO=~/Dokumente/AI/ai-SKILL-set

# Überblick: was ist veraltet?
python3 $REPO/scripts/pull_skill.py update --dry-run --target .claude/skills

# Alles updaten
python3 $REPO/scripts/pull_skill.py update --target .claude/skills
```

## Ohne Argumente aufgerufen

1. `--dry-run` ausführen
2. Ausgabe zeigen
3. Fragen: alle updaten oder nur bestimmte?
4. Dann updaten

## Nach dem Update

Kurz melden:
- Updated (welche)
- Unbekannte Skills (nicht im Registry — fremde Skills, werden übersprungen)
- Alles aktuell (wenn nichts zu tun war)

Nicht weiter erklären.
