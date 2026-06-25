# AGENTS.md

Stop. Read this before scanning the repo.

## What this repo is

A skill library — not a project. Agents are sent here to pull skills into their user's project. You are not here to work on this repo itself.

Full documentation (folder structure, quick start, adding skills): `README.md`

---

## What you are probably here to do

Ask the user which of these applies — do not guess:

1. **Pull a skill** (most common) → Which skill? Into which project?
2. **Bootstrap ticket system** → two steps: global setup (once per machine), then per-project init
3. **Something else** → Let the user describe it

---

## How to do it

**Pull a skill into your project:**
→ Browse available skills via `registry.json` (machine-readable, all skills with metadata) or browse `skills/` directly.
→ Then use the `/izg-ai-repo-pull` skill to install — no local scripts needed.

**Bootstrap tickets — global setup (once per machine):**

Deploys `tickets.md` + `doc-ids.md` to all AI agent dirs and patches their global config files.
Skip if already done (idempotent, but only run when the user asks for it).

```bash
bash scripts/setup_global_tickets.sh
```

**Bootstrap tickets — per project:**

Run from within the target project directory:

```bash
bash ~/.claude/scripts/init_tickets.sh /pfad/zum/projekt
```

This creates `tickets/` with subfolders, `.counter`, `PROTOCOL.md`, and `scripts/next_ticket_id.sh`.
Does NOT touch global agent dirs.

---

## What not to scan

| Path | Reason |
|------|--------|
| `registry.json` | Auto-generated — never edit manually. Updated automatically via pre-commit hook (`scripts/generate_registry.py`). Read `skills/` instead. |
| `scripts/` | Internal tooling for maintaining this repo — not relevant for skill usage |
| `AI/` | Planning docs — context only, not actionable |
| `hooks/` | Optional Claude Code hooks — only relevant if setting up this repo locally |
