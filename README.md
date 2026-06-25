# ai-SKILL-set

> **Agents:** Read `AGENTS.md` first — it has context, use-cases, and the fastest path to what you need.

Modular skill repository for Claude Code. Skills are not installed globally — they are pulled selectively into projects as needed. This keeps each project lean: only the skills it actually uses.

---

## What this repo is

A library of reusable Claude Code skills, organized by layer (core primitives → base skills → domain-specific compositions). Skills are Markdown files with YAML frontmatter that Claude Code loads as slash commands.

---

## Folder structure

| Folder | Purpose |
|--------|---------|
| `skills/` | All skills, organized by layer (0–4). Start here. See `skills/README.md`. |
| `scripts/` | Internal maintenance scripts: `generate_registry.py` (rebuilds registry.json), `init_tickets.sh` (bootstrap ticket system + convention docs in a project) |
| `hooks/` | Claude Code hooks: `pre-commit-registry.sh` auto-regenerates registry.json when SKILL.md files change |
| `AI/` | Planning documents (RFCs, ADRs) for this repo itself |
| `agents/` | Agent definitions (in progress) |
| `commands/` | Custom slash commands (in progress) |
| `mcps/` | MCP server configurations (in progress) |
| `workflows/` | Multi-agent workflows (in progress) |
| `infra/` | Infrastructure configs (in progress) |
| `registry.json` | Auto-generated skill index — do not edit manually |

---

## Quick start

**1. Clone this repo once (one-time setup):**
```bash
git clone https://github.com/is-noname/ai-SKILL-set.git /path/to/ai-SKILL-set
```

**2. Install the pull skill into your project:**
```bash
# Run from within your project directory:
python3 /path/to/ai-SKILL-set/scripts/pull_skill.py pull izg-ai-repo-pull --target .claude/skills
```

**3. From now on, use the skill inside Claude Code:**
```
/izg-ai-repo-pull
```
It lists available skills, resolves dependencies, and installs into `.claude/skills/`. No more manual script calls.

**4. Optionally bootstrap a ticket system and convention docs for your project:**
```bash
bash /path/to/ai-SKILL-set/scripts/init_tickets.sh
```
This creates `tickets/` and deploys `docs/tickets.md` and `docs/doc-ids.md` into your project.

**5. Link the convention docs in your project's `CLAUDE.md`:**
```markdown
@docs/tickets.md
@docs/doc-ids.md
```
Claude will load these automatically at session start.

---

## Installing a skill into a project

Once `izg-ai-repo-pull` is set up (see Quick start), use it inside Claude Code:
```
/izg-ai-repo-pull
```
It shows available skills, handles dependencies, and installs into `.claude/skills/`.

---

## Adding a skill to this repo

1. Create `skills/layer-{N}/{skill-name}/SKILL.md` with valid frontmatter (`name`, `description`, `layer`, `dependencies`)
2. The pre-commit hook regenerates `registry.json` automatically on commit
3. To regenerate manually: `python3 scripts/generate_registry.py`

See `skills/README.md` for layer rules and the full SKILL.md format.
