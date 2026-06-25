# AGENTS.md

Stop. Read this before scanning the repo.

## What this repo is

A library of reusable Claude Code skills. Skills are pulled selectively into projects — not installed globally.

Full documentation: `README.md`

---

## Why you are likely here

**Pull a skill into your project:**
```bash
python3 scripts/pull_skill.py pull <skill-name> --target .claude/skills
python3 scripts/pull_skill.py list
```

**Build or modify a skill:**
→ Read `skills/README.md` for format and layer rules. Do not edit `registry.json` manually.

**Bootstrap tickets for a project:**
```bash
bash scripts/init_tickets.sh
```
Then link `@docs/tickets.md` and `@docs/doc-ids.md` in the project's `CLAUDE.md`.

---

## What not to scan

| Path | Reason |
|------|--------|
| `registry.json` | Auto-generated — read `skills/` instead |
| `tickets/` | Internal development tracking — not relevant for skill usage |
| `AI/` | Planning docs — context only, not actionable |
| `hooks/` | Optional Claude Code hooks — only relevant if setting up this repo locally |
