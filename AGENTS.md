# AGENTS.md

Stop. Read this before scanning the repo.

## What this repo is

A skill library — not a project. Agents are sent here to pull skills into their user's project, or to build new ones. You are not here to work on this repo itself.

Full documentation (folder structure, quick start, adding skills): `README.md`

---

## What you are probably here to do

Ask the user which of these applies — do not guess:

1. **Pull a skill** (most common) → Which skill? Into which project?
2. **Build or modify a skill** → Read `skills/README.md`, then build together
3. **Bootstrap ticket system** → `bash scripts/init_tickets.sh`, then add `@docs/tickets.md` to the project's `CLAUDE.md`
4. **Something else** → Let the user describe it

---

## How to do it

**Pull a skill into your project:**
→ Browse available skills via `registry.json` (machine-readable, all skills with metadata) or browse `skills/` directly.
→ Then use the `/izg-ai-repo-pull` skill to install — no local scripts needed.

**Build or modify a skill:**
→ Read `skills/README.md` for format and layer rules.

**Bootstrap tickets for a project:**
```bash
bash scripts/init_tickets.sh
```
Then link `@docs/tickets.md` and `@docs/doc-ids.md` in the project's `CLAUDE.md`.

---

## What not to scan

| Path | Reason |
|------|--------|
| `registry.json` | Auto-generated — never edit manually. Updated automatically via pre-commit hook (`scripts/generate_registry.py`). Read `skills/` instead. |
| `scripts/` | Internal tooling for maintaining this repo — not relevant for skill usage |
| `tickets/` | Internal development tracking — not relevant for skill usage |
| `AI/` | Planning docs — context only, not actionable |
| `hooks/` | Optional Claude Code hooks — only relevant if setting up this repo locally |
