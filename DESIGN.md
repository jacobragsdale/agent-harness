# agent-harness — design

An agentic ticket loop for a solo developer: pull tickets from Azure DevOps,
triage them with an AI agent, interview the developer live, get an approved
plan, execute the change in an isolated worktree, validate it, open a PR, and
update the ticket — learning from every run.

Constraints that shaped the design:

- **No SDK, no agent platform.** The only AI runtime is the Cursor headless
  CLI (`agent -p`). Everything else is plain Python.
- **Windows-first target** (developed cross-platform). Native `agent` binary,
  PowerShell install, no symlinks, `pathlib` everywhere.
- **This repo is the orchestrator only.** All code changes happen in *other*
  local repos, registered in `repos.toml`.
- **Azure DevOps is mocked for now.** Real integration is a stub the work
  machine fills in; the demo journals every would-be write.

## Architecture

The orchestrator is a deterministic state machine; the Cursor CLI is invoked
for each *cognitive* step. Skills define all agent behavior; Python owns all
control flow, state, and side effects.

```
tickets file → [groom] → [triage] → [interview] → [plan gate] → [execute] → [validate] → [PR] → [babysit] → [retro]
                  │           │           │             │             │            │         │        │          │
             interactive  plan mode   live REPL     you approve    --force     fresh eyes  orch.  PR events  learnings
             enrichment   (read-only) (--resume)    or edit        worktree    (new sess.) does   gated      auto-append
             dup check                                                         advisory    git/gh replies+fixes
```

`loop run` orders a developer's day: babysit open PRs first (existing
commitments), then interactively groom new tickets, then work the pipeline.

### One session per ticket (from the interview on)

Triage is a short, read-only classification call in the orchestrator
workspace — it has to run before we know which repo the ticket belongs to.
The ticket's long-lived Cursor session starts at the **interview**, inside
the target repo; plan and execute `--resume` it, so your interview answers
and plan edits are literally in the executing agent's context. Validation
and retro deliberately use **fresh sessions** (fresh-eyes principle).

### State machine

Per-ticket status, persisted in `tickets/<id>/state.json`:

```
new → groomed → triaged → interviewing → awaiting_approval → approved
    → executing → validating → pr_open → done
                                  ↘ failed / rejected / deferred
```

Grooming is skippable (`new → triaged` stays legal). `pr_open` is a
*parked* state: the pipeline stops there and the **babysitter** drives it —
merged → done, closed → rejected, CI failures/review comments/conflicts →
drafted responses in the ticket's own session, gated by you, applied with
write access, replies/pushes journaled through the PR adapter. The mock
adapter answers status polls from a hand-editable `tickets/pr-inbox.json`
so PR events can be simulated in a demo.

The loop is resumable: re-running picks each ticket up at its persisted state.
Every transition also calls `TicketStore.update_status()` (journaled by the
mock).

### Ticket folders (transparency by construction)

```
tickets/<id>/
  state.json          # status, session_id, worktree, history
  triage.json         # classification: type, repo, priority, effort, recon notes
  interview.md        # full Q&A transcript
  plan-v1.md, -v2.md  # every plan revision (your comments preserved)
  execute.stream.jsonl# raw stream-json transcript of the execution run
  validation.md       # fresh-eyes findings + test command result
  retro.json          # proposed learnings and where they went
tickets/journal.jsonl # every would-be DevOps/PR write (the mock's output)
metrics.jsonl         # one row per ticket: rounds, revisions, findings, outcome
```

## Cursor CLI usage (verified against docs, 2026-07)

- Binary is `agent` (renamed from `cursor-agent`). Native Windows since
  Jan 2026: `irm 'https://cursor.com/install?win32=true' | iex`.
- Headless: `agent -p --output-format json|stream-json --trust`. **`--force`
  is required for real file edits** — read-only stages use `--mode plan`
  instead and never pass `--force`.
- Failure contract: non-zero exit + stderr, *no JSON* — exit code is the
  primary signal; JSON parsed only on success.
- `session_id` comes back in the result object; `--resume <id>` continues.
- Worktrees are built in: `-w <name> --worktree-base <branch>` (managed under
  `~/.cursor/worktrees/`).
- Auth: `CURSOR_API_KEY` env var. Model: `--model` (default `auto`;
  `agent --list-models` is the source of truth).
- Permissions: per-target-repo `.cursor/cli.json` is the safety boundary while
  `--force` is on. The execute stage is expected to run with deny rules for
  `git push`, `gh`, and secrets paths (documented in the execute skill;
  orchestrator warns if the target repo has no `.cursor/cli.json`).
- Skills: Cursor implements the Agent Skills standard. Discovery:
  `.cursor/skills/` (project) and `~/.cursor/skills/` (user). Skills load in
  headless mode and `/skill-name` works inside `-p` prompts (CLI changelog,
  May 2026). `disable-model-invocation: true` restricts a skill to explicit
  invocation.

## Skills are the behavior; Python is the plumbing

Canonical skills live in this repo under `skills/` and are **copied** (not
symlinked — Windows) to `~/.cursor/skills/` before each run, so they're
discoverable from any target repo workspace.

- **Stage skills** (`disable-model-invocation: true`, invoked as
  `/ticket-triage` etc. by the orchestrator): `backlog-groom`,
  `ticket-triage`, `ticket-interview`, `ticket-plan`, `ticket-execute`,
  `ticket-validate`, `pr-babysit`, `ticket-retro`. Each defines the stage's
  job and an exact JSON output contract the orchestrator parses.
- **Task-type playbooks** (referenced by stage prompts after triage
  classifies the ticket): `fix-bug`, `new-feature`, `prod-issue`, `qa-test`,
  `infra-maintenance`.

JSON contract convention: skills end their answer with a single fenced
```json block; the orchestrator extracts the last such block. One retry via
`--resume` ("re-emit valid JSON only") on parse failure.

## Interactive interview & plan gate (fully live)

- **Interview**: the skill emits `{questions: [{id, question, why_it_matters,
  options?}]}`. The terminal renders each with its rationale; you answer
  free-text (`skip` / `you decide` allowed). Answers are sent back via
  `--resume`; the agent asks follow-up rounds or declares readiness (hard cap
  3 rounds).
- **Plan gate**: plan rendered as markdown, then:
  `[a]pprove · [c]omment (change requests → revised plan, unlimited cycles) ·
  [e]dit in $EDITOR (diff fed back) · [r]eject · [d]efer`.
  Every revision is saved; nothing executes without an explicit `a`.

## Validation (deliberately shallow, v1)

A fresh session in plan mode reviews `git diff` in the worktree against the
ticket's acceptance criteria, plus the repo's `test_command` from
`repos.toml` if one is configured. Findings **do not block** — they're shown
to you at the PR gate and you decide. (Test coverage on the target repos is
known-poor; deepening validation is a later iteration.)

## PR & ticket updates

The orchestrator — not the agent — does the deterministic side effects,
following Cursor's own "restricted" CI pattern: the execute agent may `git
commit` in its worktree but never push; the orchestrator pushes and calls
`PRClient.create_pr()` and `TicketStore` transitions. Mock implementations
journal to `tickets/journal.jsonl`; `AzDevOpsTicketStore` / `AzReposPRClient`
are empty stubs for the work machine.

## Self-improvement loop

After every terminal state (done *or* failed), `ticket-retro` runs in a fresh
session with the run artifacts and mines: questions the agent should not have
needed to ask, plan edits you made, validation findings, repeated patterns.
Output routes two ways:

1. **Workflow knowledge → auto-append** one dated line per learning to the
   relevant skill's `LEARNINGS.md` in *this* repo (then re-sync). Format
   matches the house convention:
   `- YYYY-MM-DD: <what happened> → <what to do instead>`.
2. **Repo knowledge → gated.** Proposed edits to the target repo's
   `AGENTS.md` / `.cursor/rules` are shown as a diff at the same approval UI;
   if approved they're applied in the worktree and ride the ticket's PR.

When a skill's LEARNINGS.md exceeds a threshold (~8 entries), the retro stage
files a ticket *against this repo* to fold learnings into SKILL.md — the loop
maintains itself through its own pipeline.

## Configuration

- `repos.toml` — registry mapping DevOps project/tags → local repo path,
  default branch, optional test command. Triage picks the repo from this;
  ambiguity becomes an interview question.
- `.env` (house convention: `.env.example` committed, `.env` → active env) —
  `CURSOR_API_KEY`, `LOOP_MODEL`, `LOOP_TICKETS_FILE`, `EDITOR`.
- Everything runs as `uv run --env-file .env loop …` (single entry point).

## Out of scope for v1

Real Azure DevOps calls, real `git push`/PR creation, hooks, sandbox config,
parallel ticket execution (design supports it — worktrees + per-ticket state
— but the interview is serial by nature), deep validation.
