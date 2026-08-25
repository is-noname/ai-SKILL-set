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
→ If you have the `/izg-ai-repo-pull` skill, use it to install — it resolves dependencies automatically.
→ If you do NOT have that skill (fresh Vibe/Gemini/Codex agents won't), use the repo-local script instead:

```bash
python3 scripts/pull_skill.py list                          # show all skills
python3 scripts/pull_skill.py pull izg-kissd --target .claude/skills   # replace izg-kissd with the skill you want
```

**Bootstrap tickets — global setup (once per machine, per agent):**

Deploys `tickets.md` + `doc-ids.md` to your own agent dir and patches your global config.
Each agent runs this only for itself — pass your own dir:

```bash
bash scripts/setup_global_conventions.sh ~/.vibe    # if you are Vibe
bash scripts/setup_global_conventions.sh ~/.gemini  # if you are Gemini
bash scripts/setup_global_conventions.sh ~/.codex   # if you are Codex
bash scripts/setup_global_conventions.sh ~/.claude  # if you are Claude
```

**Bootstrap tickets — per project:**

Use the repo-local script (agent-neutral — works regardless of which agent you are):

```bash
bash scripts/init_tickets.sh /pfad/zum/projekt PREFIX   # PREFIX: 2-6 Grossbuchstaben
```

Expected output: `tickets/ ready in <pfad> (Prefix <PREFIX> in PROTOCOL.md verankert, scripts deployed)` — without a prefix argument, the script prints a placeholder variant instead ("Prefix nicht gesetzt, ..."); that's expected, not an error.

(After global setup the same script also lives at `<your-agent-dir>/scripts/init_tickets.sh`, e.g.
`~/.vibe/scripts/init_tickets.sh` — but the repo-local one above always works.)

This creates `tickets/` with subfolders, `.counter`, `PROTOCOL.md`, and `scripts/next_ticket_id.sh`.
Does NOT touch global agent dirs.

---

## If something fails

Don't fail silently — report the exact command and error to the user. Common cases:

- **Script not executable** → run with an explicit interpreter (`bash scripts/...` / `python3 scripts/...`) instead of `./script`.
- **Target project path doesn't exist** → stop and ask the user for the correct path; do not create it blindly.
- **`/izg-ai-repo-pull` skill missing** → fall back to `python3 scripts/pull_skill.py` (see "How to do it").

---

## What not to scan

| Path | Reason |
|------|--------|
| `registry.json` | Auto-generated — never edit manually. Updated automatically via pre-commit hook (`scripts/generate_registry.py`). Read `skills/` instead. |
| `scripts/` | Don't scan for *skill usage*. For ticket bootstrap you DO run two of them — see "How to do it" above (`setup_global_conventions.sh`, `init_tickets.sh`). |
| `AI/` | Planning docs — context only, not actionable |
| `hooks/` | Optional Claude Code hooks — only relevant if setting up this repo locally |
