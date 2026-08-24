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
| `AI/` | Planning documents (RFCs, ADRs) for this repo itself — local only, not in the clone |
| `registry.json` | Auto-generated skill index — do not edit manually |

**Planned, currently empty** — reserved names, nothing to read there yet:
`agents/` (agent definitions) · `commands/` (custom slash commands) · `mcps/` (MCP server configs) ·
`workflows/` (multi-agent workflows) · `infra/` (infrastructure configs) · `testing/` (local only).

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

**4. Optionally set up the ticket system. Two levels:**

*a) Global, once per machine per agent* — deploys the convention docs
`tickets.md` + `doc-ids.md` into your agent dir and patches your global config
(`~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`, …) to load them:
```bash
bash /path/to/ai-SKILL-set/scripts/setup_global_conventions.sh ~/.claude
```

*b) Per project* — run from within the target project:
```bash
bash /path/to/ai-SKILL-set/scripts/init_tickets.sh
```
Expected output: `tickets/ ready in <pfad> (Prefix <PREFIX> in PROTOCOL.md verankert, scripts deployed)` — without a prefix argument, the script prints a placeholder variant instead ("Prefix nicht gesetzt, ..."); that's expected, not an error.

This creates `tickets/` (with subfolders), `.counter`, a project-local
`tickets/PROTOCOL.md`, and `scripts/next_ticket_id.sh`. It does **not** copy the
convention docs into the project — `PROTOCOL.md` points back to the global
`tickets.md`/`doc-ids.md` from step a). So there is nothing to `@`-link in the
project's `CLAUDE.md`; the global config already loads the conventions.

To understand *how* the ticket system works internally (ID assignment, status hook,
bootstrap levels), see the architecture guide:
[`docs/ticket-system-architecture.en.md`](docs/ticket-system-architecture.en.md)
(Deutsch: [`docs/ticketsystem-architektur.md`](docs/ticketsystem-architektur.md)).

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
