# TODO — handoff notes

Written for the next Claude Code (or human) session picking this up.
Read [DESIGN.md](DESIGN.md) first for the architecture; read
[AGENTS.md](AGENTS.md) for commands and conventions. Status as of
2026-07-05: **the orchestrator is complete and tested, but has never run
against the real Cursor CLI** — it was built on a machine without the
binary. The first Windows run will be the shakedown.

## 1. Azure DevOps integration (the big one)

Everything DevOps-facing is behind two protocols; the loop only ever talks
to these, so going live is implementing two classes and swapping them in
`_build_context` in [cli.py](src/agent_harness/cli.py):

- `AzDevOpsTicketStore` in [tickets.py](src/agent_harness/adapters/tickets.py)
  - `fetch_tickets()` — query work items (WIQL via `az boards query` or the
    REST API), map to `Ticket` (see §2).
  - `update_status()` — `az boards work-item update --id <id> --state <s>`.
    NOTE: the loop passes *its own* state names (`triaged`, `in_progress`,
    `awaiting_approval`, `pr_open`, `done`, `failed`, `rejected`,
    `deferred`); real DevOps workflows have their own state set, so this
    method needs a mapping table (probably config in repos.toml or .env).
  - `add_comment()` — work-item discussion comment.
- `AzReposPRClient` in [prs.py](src/agent_harness/adapters/prs.py)
  - `push_branch()` — `git -C <worktree> push -u origin <branch>` (the
    execute agent commits but is forbidden to push).
  - `create_pr()` — `az repos pr create` (or `gh pr create`).
  - `get_pr_status()` — merge state + build status + unresolved review
    threads, mapped to `PRStatus` (the babysitter polls this; the mock
    reads `tickets/pr-inbox.json`).
  - `post_reply()` — reply on a PR thread.
  - The branch name == worktree name == `ticket-<id>`; the worktree path is
    in `tickets/<id>/state.json` under `worktree_path`.

Jacob has an existing program on his work machine intended to handle the
real reads/writes — coordinate with that before implementing from scratch;
these stubs may end up as thin shims around it.

Auth for whichever path: PAT via env var (add to `.env.example`), never
hardcoded.

## 2. Ticket data shape

Current contract (what `MockTicketStore.fetch_tickets` +
`Ticket.from_dict` in [models.py](src/agent_harness/models.py) expect):

```json
{ "tickets": [ { "id": "4211", "title": "...", "description": "...",
    "project": "Billing", "tags": ["bug"], "link": "https://...",
    "status": "New" } ] }
```

- A bare top-level array also works; `id` may be int (normalized to str);
  unknown fields land in `Ticket.extra` and are ignored.
- Jacob's real export file has "link, description, project, tag etc" — when
  wiring it up, expect at least: `tags` as a semicolon-joined string (DevOps
  convention) instead of a list, and `description` as HTML. Both conversions
  belong in `Ticket.from_dict` / the store, NOT downstream: strip HTML to
  text (agents don't need markup) and split tags on `;`.
- If a field is missing, prefer defaulting over crashing — triage handles
  sparse tickets fine.

## 3. First contact with the real Cursor CLI (Windows shakedown list)

Facts below were verified against cursor.com/docs in July 2026 but never
executed by this codebase. Check in this order:

1. `agent --version`, `agent --list-models`, `CURSOR_API_KEY` set.
2. Single JSON result parse: `run()` in
   [cursor.py](src/agent_harness/cursor.py) expects one JSON object on
   stdout with `result`, `session_id`, `is_error`.
3. stream-json event shapes: `ui.narrate_stream_event` guesses field names
   from doc examples (`tool_call` + `subtype: started`). Fix against a real
   `execute.stream.jsonl` transcript (they're saved per ticket — read one).
4. `--resume <session_id>` across invocations with the SAME `--workspace`
   (interview → plan → execute chain).
5. `--resume` combined with `-w/--worktree` (execute resumes the interview
   session while entering a new worktree) — if the CLI rejects the combo,
   fall back to a fresh session for execute whose prompt embeds the final
   plan text (plan-of-record is on disk, so this is a small change in
   [execute.py](src/agent_harness/stages/execute.py)).
6. Worktree path: the execute skill's contract makes the agent report
   `worktree_path`; the fallback guess in
   [validate.py](src/agent_harness/stages/validate.py) is
   `~/.cursor/worktrees/<repo-dir-name>/<worktree-name>` — verify.
7. Re-drive of an interrupted `EXECUTING` ticket passes `--worktree` again
   for a worktree that already exists — check the CLI accepts that.
8. Babysitter draft/apply cycle: the draft call resumes the ticket session
   with `--workspace <worktree_path>` while the session was created with
   `--workspace <repo>` — verify resume tolerates the workspace change
   (same fallback as #5 if not: fresh session with the plan + diff in the
   prompt).

## 4. Safety config for target repos

Before the first `--force` run on a real repo, create
`<repo>/.cursor/cli.json`:

```json
{ "permissions": { "deny": [
    "Shell(git:push)", "Shell(gh)", "Shell(az)",
    "Write(.env*)", "Write(**/secrets/**)"
] } }
```

The orchestrator does not currently warn when a target repo lacks this
file — adding that warning to `run_execute` would be a good small
improvement.

## 5. Smaller known gaps / ideas

- **Retro self-ticketing**: at ≥8 LEARNINGS entries we only print a warning
  ([retro.py](src/agent_harness/stages/retro.py)). Intended design: append a
  synthetic maintenance ticket (project = this repo) to the tickets source
  so the loop folds learnings via its own pipeline.
- **Interview round counting vs. skill cap**: MAX_ROUNDS=3 is enforced by
  the orchestrator; the skill text says "at most 2 in practice". Fine, but
  keep them in sync if you change either.
- **`loop status` shows every fetched ticket as `new`** once `run` has seen
  it (opening a workspace creates state.json). Cosmetic; filter if it
  annoys.
- **Worktree cleanup**: nothing removes `~/.cursor/worktrees/ticket-*` after
  a PR merges. Add a `loop cleanup <id>` command eventually.
- **DevOps state mapping** (see §1) and **PR body format** (currently the
  raw final plan markdown) will both need taste passes with real tickets.
- **Ticket splits at grooming**: the groom stage records split suggestions
  but can't create tickets (mock store is read-only for creation). When the
  real store lands, add `create_ticket()` and wire the split action.
- No LICENSE file yet — decide before advertising the repo.
- Bigger-picture enhancements (digest, graduated autonomy, patrols, batch
  interviews) live in [IDEAS.md](IDEAS.md).

## What is deliberately NOT a TODO

- Deep validation (test-writing validator): postponed on purpose — target
  repos have weak tests; revisit after the loop has produced a few PRs.
- Hooks, sandbox flags: skipped for v1; permissions config is the boundary.
- Any SDK/agent-platform usage: hard constraint, do not introduce one.
