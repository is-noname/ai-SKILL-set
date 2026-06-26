# Ticket System — Architecture & How It Works

This guide explains **how** the ticket system is built and how it operates
internally — for understanding the mechanics, not as a convention reference.

> 🇩🇪 Deutsche Version: [`ticketsystem-architektur.md`](./ticketsystem-architektur.md)

> **Placeholder note:** Throughout this document, `PRJ` is a stand-in for the
> **per-project prefix**. Every project defines its own prefix in `docs/doc-ids.md`
> (e.g. a short three-letter code per repo). `PRJ`, `NNN`, and names like
> `my-project` are generic placeholders — **not** fixed or reserved identifiers.

| You want… | Read… |
|-----------|-------|
| the rules/fields (what goes in, what it's called) | `docs/tickets.md` |
| the short lookup rules inside a project | `tickets/PROTOCOL.md` |
| **to understand how the mechanics work** | **this document** |

---

## 1. The idea in one sentence

Tickets are **Markdown files in folders**. The folder a file lives in *is* its
status. There is no database, no backend, no server — just files, a counter, a hook,
and three shell scripts. Everything is git-friendly, diffable, and shared across
multiple agents (e.g. Claude, Gemini, Codex).

**Consequence:** You change a ticket's status by editing the `status:` field in its
frontmatter. A hook then moves the file into the matching folder. Folder and
frontmatter status are always redundant — but the frontmatter is the source of
truth, the folder is just its projection.

---

## 2. Component map

```
project/
├── scripts/
│   ├── init_tickets.sh          # bootstrap per PROJECT (creates tickets/)
│   ├── next_ticket_id.sh        # hands out the next free ID (atomic)
│   └── setup_global_tickets.sh  # bootstrap per AGENT (deploys convention globally)
├── hooks/
│   └── ticket-mover.sh          # moves tickets on status change
├── docs/
│   ├── tickets.md               # convention (deployed into the agent dir)
│   ├── doc-ids.md               # project prefix + doc-id scheme (deployed globally too)
│   └── ticket-system-architecture.en.md  # this document
└── tickets/
    ├── .counter                 # highest number assigned so far
    ├── PROTOCOL.md              # project-local short rules
    ├── open/                    # status: open
    ├── in-progress/             # status: in-progress
    ├── blocked/                 # status: blocked
    └── done/                    # status: done  (final archive)
```

| Component | Role | When active |
|-----------|------|-------------|
| `tickets/<status>/` | storage; folder name = status | always |
| `.counter` | remembers the highest ID number | on ID assignment |
| `next_ticket_id.sh` | computes & reserves the next ID | manually, before creating a ticket |
| `ticket-mover.sh` (hook) | keeps folder and `status:` in sync | automatically after each Edit/Write |
| `init_tickets.sh` | builds `tickets/` in a project | once per project |
| `setup_global_tickets.sh` | deploys the convention into the agent dir | once per agent/machine |
| `doc-ids.md` | provides the project prefix `PRJ` | on ID assignment |

---

## 3. Ticket lifecycle

```
                  next_ticket_id.sh PRJ
                          │
                          ▼
        ┌────────────────────────────────────────┐
        │  create file: open/PRJ-T-NNN_…​.md       │
        │  status: open                            │
        └────────────────────────────────────────┘
                          │
    status: in-progress   │   (hook moves → in-progress/)
                          ▼
        ┌────────────────────────────────────────┐
        │             work happens                 │
        └────────────────────────────────────────┘
            │                       │
status: done│                       │ status: blocked
            ▼                       ▼
      done/ (archive)          blocked/
                                    │ status: open
                                    ▼
                                 open/  (never directly → in-progress)
```

**Rules the mechanics enforce or expect:**
- Every status change = one history entry (when, why, what's done/open).
  No script enforces this — it's convention and part of review quality.
- `blocked/` always goes back to `open/`, never straight to `in-progress/`.
- `done/` is never deleted — it's the archive and the source for the
  self-healing ID assignment (see §4).

---

## 4. ID assignment — how `next_ticket_id.sh` works

Invocation (the argument is the project prefix):
```bash
bash scripts/next_ticket_id.sh PRJ     # → PRJ-T-019
```

The script is **self-healing** and **collision-safe**. Flow:

```
1. flock on .counter.lock           → serializes concurrent calls
2. counter   = value from .counter  → non-digits stripped (no crash)
3. max_exist = highest PRJ-T-NNN     → across ALL folders (grep over tickets/)
4. floor     = max(counter, max_exist)
5. next      = floor + 1
6. .counter  = next                  → persist
7. output    = PRJ-T-019
```

**Why this way?**

- **Self-healing (step 3):** The counter is only a cache. The true highest number
  comes from the tickets that actually exist. If the counter is lost, drifts, or a
  project is bootstrapped later, `grep` across all folders still yields the correct
  base. That gives exactly **one source of truth**.
- **Crash-resistant (step 2):** `tr -dc '0-9'` strips non-numeric garbage from
  `.counter`. Worst case the counter reads 0 — step 3 catches that.
- **Collision-safe (step 1):** Without a lock, two agents running concurrently would
  both read the same `floor` and get the same ID. `flock` on fd 9 over `.counter.lock`
  serializes the read-compute-write. If `flock` is missing on the system, it proceeds
  without a lock — self-healing corrects drift afterwards (only real-time uniqueness
  is then not guaranteed).

> The prefix `PRJ` is **not** part of the script — it comes in as an argument and
> originates from `docs/doc-ids.md` (single source of truth for project prefixes).
> Every project has its own.

---

## 5. Status synchronization — how the hook works

`hooks/ticket-mover.sh` is a **PostToolUse hook**: Claude Code calls it after every
`Edit`/`Write` and passes JSON over stdin. The hook decides for itself whether it's
responsible.

```
Edit/Write on a file
        │
        ▼
  Is it an Edit/Write?                    no  → exit (do nothing)
        │ yes
  Is the file under */tickets/*?          no  → exit
        │ yes
  Does it have valid frontmatter          no  → exit
  (id: PRJ-T-NNN)?
        │ yes
  Is status: a known value?               no  → exit
  (open|in-progress|blocked|done)
        │ yes
  folder name == status?                  yes → exit (already correct)
        │ no
  Does the target file already exist?     yes → WARN, do NOT move
        │ no
        ▼
  mv -n  →  tickets/<status>/<file>
  message on stderr
```

**Key properties:**
- **Idempotent & defensive:** Acts only on real ticket files with valid frontmatter
  and a known status. Everything else is left untouched.
- **Collision protection:** If a file of the same name already exists in the target
  folder (e.g. the same ID moved manually into two folders), the hook does **not**
  move and warns on stderr — no silent overwrite, no data loss. `mv -n` is the second
  safeguard.
- **The hook only moves — it never changes content.** The `status:` field is always
  set by a human or agent.

---

## 6. Two bootstrap levels

The system is set up at two levels — easy to confuse:

| | `setup_global_tickets.sh` | `init_tickets.sh` |
|---|---|---|
| **Level** | per AI agent (global) | per project |
| **How often** | once per agent/machine | once per project |
| **What** | deploys `tickets.md` + `doc-ids.md` **and** `init_tickets.sh` into the agent dir and patches its config | creates the `tickets/` folder structure, `.counter`, `PROTOCOL.md` and `next_ticket_id.sh` |
| **Target** | `~/.claude`, `~/.codex`, `~/.gemini`, `~/.vibe` | any project folder |
| **Config file** | `CLAUDE.md` / `instructions.md` / `GEMINI.md` / `AGENTS.md` | — |

**Global level** — each agent knows the convention system-wide:
```bash
bash scripts/setup_global_tickets.sh ~/.claude
bash scripts/setup_global_tickets.sh ~/.codex
```
The script obtains the convention docs **and** `init_tickets.sh` in this order:
1. locally from the repo (when checked out) — the normal case
2. via `curl` from `RAW_BASE` (derived from `git remote`, overridable via
   `AISKILLSET_RAW_BASE`)
3. if neither is reachable → clear error message + exit 1 (no silent skip)

`init_tickets.sh` is placed into `$AGENT_DIR/scripts/` so the bootstrap hint patched
into the agent config below actually points at an existing script (each agent in its
own dir, not hard-coded `~/.claude`).

**Project level** — a concrete project gets its `tickets/` (the path points at the
agent's own dir, `~/.claude` shown as an example):
```bash
bash ~/.claude/scripts/init_tickets.sh /path/to/project
```
Idempotent: re-running adds a missing counter / the current `next_ticket_id.sh`
without overwriting existing tickets or `PROTOCOL.md`.

---

## 7. Coupling with the doc-ids system

The ticket system and the doc-ids (`docs/doc-ids.md`) share the **project prefix**:

- Ticket IDs: `PRJ-T-NNN` → `{PREFIX}-T-{NUMBER}`
- Doc IDs: `{TYPE}-{DATE}-{SEQ}` (e.g. `AUD-{YYYYMMDD}-001_…`)

Links in both directions:
- **Document → tickets:** an audit/report proposes tickets; in the ticket the
  `source:` field points back to the triggering document.
- **Tickets → group:** related tickets share a `group:` field (replaces loose TODO
  lists). Query (the group slug is free-form):
  ```bash
  grep -rl "^group: <group-slug>" tickets/
  ```

`FIX`, `FIXR`, `TODO` are **not** doc-ids — they are captured as tickets.

---

## 8. Multi-agent operation

Multiple agents work on the same `tickets/`:
- `created-by:` and `assigned:` record who created a ticket and who is responsible
  (`claude` / `gemini` / `codex` / `me`).
- ID assignment is protected against race conditions via `flock` (§4).
- Since everything is files, coordination runs through Git: tickets are committed,
  conflicts are ordinary merge conflicts on text files.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Ticket stays in the wrong folder after a status change | Hook not installed/active, or frontmatter invalid (check `id:`/`status:`). Status must be exactly `open`/`in-progress`/`blocked`/`done`. |
| "target … already exists — not moved" | Same ID lives in two folders. Resolve manually, then set the status again. |
| `next_ticket_id.sh` hands out the same ID twice | `flock` missing on the system → install it (util-linux). Self-healing corrects drift on the next run. |
| Two tickets with the same number exist | Rename one (fetch a higher free number via the script), note it in the history. |
| `.counter` shows an absurd value | Doesn't matter — the script takes the max of counter and real tickets. Optionally reset it to the highest assigned number. |
| Global setup aborts with a fetch error | Check out the repo locally or set `AISKILLSET_RAW_BASE` to a reachable source. |

---

## 10. Design decisions in brief

- **Files instead of a DB:** diffable, git-mergeable, readable without tooling,
  agent-agnostic.
- **Folder = status:** the status is visible at a glance (`ls tickets/open`) without
  opening any file.
- **Frontmatter is the truth, the hook is only the projection:** you edit a field,
  not the file path — less error-prone and easier for agents.
- **Counter as a cache, not an authority:** prevents a lost/wrong counter from
  permanently corrupting the system.
