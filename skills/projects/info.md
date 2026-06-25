# Projects

**Zweck:** Projekt-Profile — definieren welche Skills ein bestimmtes Projekt braucht.

**Workflow:** Der `/izg-ai-repo-pull` Skill scannt diesen Ordner dynamisch und zeigt eine Auswahlliste. Du wählst ein Profil, er löst alle Dependencies auf und kopiert die Skills nach `.claude/skills/` im Projekt.

**Struktur:**
```
projects/
└── {project-name}/
    ├── skills.json      # Benötigte Skills + Sets (Short-Names)
    └── config.json      # Projekt-spezifische Einstellungen (optional)
```

**skills.json Format (Short-Names):**
```json
{
  "sets": ["grilling"],
  "skills": ["izg-starter-icon-mkr"]
}
```

- `sets`: Vorgefertigte Skill-Kombinationen aus `sets/`
- `skills`: Einzelne Skills zusätzlich zum Set
- Layer-0-Skills nie direkt eintragen — kommen automatisch als transitive Dependency
- Konflikte (Skill in Set + einzeln): Einzelner Skill gewinnt
