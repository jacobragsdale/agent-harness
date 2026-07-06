# agent-harness

**Your ticket queue, worked by an agent that interviews you first.**

Every developer's day is the same pile: new features, bug reports, prod
issues, QA passes, infra chores. Most of that work has a shape an AI agent
can execute — but only after the questions a human would ask get asked. This
project is that missing middle: an agentic loop that takes your Azure DevOps
tickets and drives each one through

```
groom → triage → interview YOU → plan → your approval → execute → fresh-eyes validation → PR → babysit → retro
```

with a hard rule: **nothing executes until you've been interviewed and have
approved a concrete plan.** You're not reviewing a surprise 800-line diff at
the end; you're making the calls that matter at the start, in a live
terminal Q&A, then editing the plan until it's right.

Built on the [Cursor headless CLI](https://cursor.com/docs/cli) and plain
Python — no agent SDK, no orchestration platform. The loop is a
deterministic state machine you can read in an afternoon; all the
intelligence lives in version-controlled [skills](skills/).

## Why it's interesting

- **It works your day in the right order.** `loop run` first checks on open
  PRs (CI failures, review comments — drafted responses, gated by you),
  then picks a batch and grooms it, and only then takes on new work.
- **Built for a 100-ticket backlog.** Each session, the picker ranks what's
  workable — in-flight work first, then prod issues, stale-sprint
  leftovers, priority — and suggests 5 (`--batch N`) with a one-line "why"
  each. Take or ignore each suggestion; ignored tickets are left completely
  untouched. Finish the batch and it offers to pick 5 more.
- **Live interview, not fire-and-forget.** The agent explores the target
  repo first, then asks only the questions the code can't answer — each with
  a "why this matters." Your answers land directly in the context of the
  session that later writes the code (`--resume` all the way through).
- **A real approval gate.** Plans arrive as markdown with an explicit file
  list, out-of-scope section, and validation strategy. Approve, request
  changes (unlimited rounds), or open it in your editor and rewrite it —
  your edit becomes the plan of record.
- **Fresh-eyes validation.** A *separate* agent session with no memory of
  writing the code reviews the diff against the ticket. Findings are
  advisory; you decide at the PR gate.
- **It gets better every ticket.** A retro stage mines each run — wasted
  questions, plan corrections you made, validation catches — and appends
  dated learnings to the relevant skill's `LEARNINGS.md`. Repo-specific
  discoveries become gated proposals for that repo's `AGENTS.md`, riding the
  ticket's own PR.
- **Everything on disk.** Per-ticket folders hold the interview transcript,
  every plan revision, the raw execution stream, and validation findings.
  `tickets/journal.jsonl` records every write the loop *would* make to
  DevOps. `metrics.jsonl` tracks rounds/revisions/outcomes per ticket.
- **Safety by construction.** The agent works in an isolated git worktree,
  may commit but never push; PRs and ticket updates are deterministic
  orchestrator code behind swappable adapters (mocked by default). The state
  machine literally has no edge from "interviewing" to "executing" that
  skips your approval.

## Status

Orchestrator complete and tested (unit tests, ruff, basedpyright clean);
Azure DevOps and PR creation are **mocked** — writes are journaled, not
performed. It has not yet run against a live Cursor CLI; see
[TODO.md](TODO.md) for the shakedown checklist and integration handoff, and
[DESIGN.md](DESIGN.md) for the architecture and the design conversation
behind it.

## Requirements

- [uv](https://docs.astral.sh/uv/) — that's it for the orchestrator. uv installs Python 3.11 itself.
- [Cursor CLI](https://cursor.com/docs/cli) for actual runs:
  - Windows (PowerShell): `irm 'https://cursor.com/install?win32=true' | iex`
  - macOS/Linux: `curl https://cursor.com/install -fsS | bash`

## Setup

    uv sync
    uv run pre-commit install
    cp .env.example .env.dev            # fill in CURSOR_API_KEY
    ln -sf .env.dev .env                # .env points at the active environment
    cp repos.example.toml repos.toml    # register your local repos

On Windows (no symlinks): copy instead — `copy .env.dev .env`.

## Configuration

Environments live in `.env.dev` / `.env.staging` / `.env.prod` (gitignored);
`.env` is a symlink/copy of the active one. All variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `CURSOR_API_KEY` | Cursor CLI auth for headless runs | `key_...` |
| `LOOP_MODEL` | Model passed to `agent --model` | `auto` |
| `LOOP_TICKETS_FILE` | Ticket export the mock store reads | `data/tickets.sample.json` |
| `LOOP_AGENT_BIN` | Override the Cursor binary name/path | `agent` |
| `EDITOR` | Editor for the plan gate's `[e]dit` action | `code --wait` |

`repos.toml` (copy of [repos.example.toml](repos.example.toml)) registers
the local repos the loop may work in and how tickets map to them.

## Running

| Command | What it does |
|---------|--------------|
| `uv run --env-file .env loop run` | Babysit open PRs, pick a batch of 5, groom it, work it |
| `uv run --env-file .env loop run --batch 3` | Smaller batches per pick round |
| `uv run --env-file .env loop run --ticket 4211` | Process a single ticket (no picker) |
| `uv run --env-file .env loop run --max 1 --skip-groom` | One ticket, no grooming pass (demo mode) |
| `uv run --env-file .env loop groom` | Interactive grooming pass only |
| `uv run --env-file .env loop babysit` | One pass over open PRs only |
| `uv run --env-file .env loop status` | Table of every ticket's pipeline state |
| `uv run --env-file .env loop sync-skills` | Copy `skills/` to `~/.cursor/skills` |

To simulate PR events for the babysitter in demo mode, edit
`tickets/pr-inbox.json` (format documented in
[prs.py](src/agent_harness/adapters/prs.py)) — add a review comment or set
`"ci": "failing"`, then run `loop babysit`. Future directions live in
[IDEAS.md](IDEAS.md).

The sample tickets in [data/tickets.sample.json](data/tickets.sample.json)
cover the five task types (bug, feature, prod issue, QA, infra), each with a
matching playbook skill.

## Going live

Implement the two stub classes and swap them in `cli.py:_build_context` —
the rest of the loop is oblivious:

- `AzDevOpsTicketStore` in [tickets.py](src/agent_harness/adapters/tickets.py)
- `AzReposPRClient` in [prs.py](src/agent_harness/adapters/prs.py)

[TODO.md](TODO.md) §1–§2 documents exactly what they must do and the ticket
data shape.

## Development

    uv run pytest                                  # tests
    uv run ruff check --fix && uv run ruff format  # lint + format
    uv run basedpyright                            # type check

Pre-commit runs all of the above on commit. Agent behavior changes go in
`skills/*/SKILL.md`, not in Python prompt strings — see
[AGENTS.md](AGENTS.md).
