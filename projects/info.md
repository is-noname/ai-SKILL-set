# Projects

**Zweck:** Projekt-Konfigurationen und Skill-Auswahl.

**Struktur:**
- Jedes Projekt hat eigenen Ordner unter `projects/`
- Jeder Projekt-Ordner enthält:
  - `skills.json` - Liste der benötigten Skills (Referenzen auf Skills aus Layer 0-3)
  - `config.json` - Projekt-spezifische Einstellungen
  - Optional: `README.md` - Projektbeschreibung

**Beispiel-Struktur:**
```
projects/
└── mein-projekt/
    ├── skills.json
    ├── config.json
    └── README.md
```

**skills.json Format:**
```json
{
  "skills": [
    "layer-0-core/logging",
    "layer-1-base/file-utils",
    "layer-2-domain/finance/marktanalyse",
    "layer-3-project/mein-projekt/custom-logic"
  ],
  "version": "1.0.0"
}
```

**Vorteile:**
- Nur benötigte Skills werden geladen
- Klare Trennung zwischen globalen und projekt-spezifischen Skills
- Einfache Wartung und Updates
