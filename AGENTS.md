# AGENTS.md

## Setup

- `uv sync` — the only setup step. Python 3.11, managed by uv.
- NEVER `pip install`. NEVER create requirements.txt. All dependencies go in
  `pyproject.toml` via `uv add` (dev deps: `uv add --dev`).

## Commands

- Run: `uv run --env-file .env loop run` (also `loop status`, `loop sync-skills`)
- Test: `uv run pytest`
- Lint/format: `uv run ruff check --fix && uv run ruff format`
- Type check: `uv run basedpyright`

## Conventions

- All dependency and tool config lives in `pyproject.toml` — no other config
  files for packaging, ruff, or basedpyright.
- Env vars: code reads `os.environ` only. Any new variable must be added to
  `.env.example` with a comment.
- New entry points get a `[project.scripts]` entry AND a row in the README
  Running table.
- Commits must pass pre-commit (ruff, basedpyright, uv-lock).
- Windows is the deployment target: `pathlib` everywhere, no symlinks, no
  POSIX-only shell in subprocess calls.

## Architecture (read DESIGN.md before structural changes)

- `src/agent_harness/loop.py` dispatches tickets by persisted status;
  stages in `src/agent_harness/stages/` each wrap one Cursor CLI call.
- Agent behavior lives in `skills/*/SKILL.md`, NOT in Python prompt strings —
  change skills to change behavior. The retro stage auto-appends to
  `skills/*/LEARNINGS.md`; fold learnings into SKILL.md deliberately, never
  edit SKILL.md from code.
- All terminal I/O goes through `ui.py`; stages must stay non-interactive
  apart from it (tests replace `ui`).
- External side effects only via the `TicketStore` / `PRClient` protocols in
  `src/agent_harness/adapters/` — mocks journal to `tickets/journal.jsonl`.

## Gotchas

- `tickets/` and `metrics.jsonl` are runtime state, gitignored — never
  commit them.
- The Cursor CLI binary is `agent` (not `cursor-agent`); real runs need it
  on PATH plus `CURSOR_API_KEY`.
