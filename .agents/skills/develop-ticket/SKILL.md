---
name: develop-ticket
description: "Use when the developer asks to implement, develop, or ship one accepted work brief or ticket. Works in the selected target repository through understanding, explicit plan approval, implementation, validation, and a pull request."
disable-model-invocation: true
---

# Develop ticket

Implement exactly one accepted work brief. Keep the agent conversation focused
on the target repository; the brief and the small local state file are the
durable record, not an opaque resumed session. Do not re-rank the backlog or
silently expand scope.

## When to use

Run this skill explicitly for requests such as:

- `/develop-ticket 4211`
- “Implement the ready ticket 4211.”
- “Resume the approved work brief for the invoice retry fix.”

Do not use it to choose backlog work. Run `/backlog-triage` first when there
is no accepted brief.

## Workflow

When this workflow says `state.py` or `validate.py`, run the named script from
this skill's `scripts/` directory with `uv run`.

1. Read `.agents/work-items/<ticket-id>/BRIEF.md`. Refuse to start if its
   status is not `ready`. Resolve the target repository path from the brief;
   ask the developer if it is missing or ambiguous.
2. Run `state.py show <ticket-id>`. If no state exists, run `state.py init
   <ticket-id>`. Resume the printed stage; do not skip it or edit `state.json`
   directly.
3. In `understand`, inspect only the target repository and the brief. Ask the
   developer only questions the repository and brief cannot answer. Write
   `.agents/work-items/<ticket-id>/PLAN.md` with: intent, acceptance criteria,
   affected files, implementation steps, validation commands, risks, and out
   of scope. Run `state.py advance <ticket-id>` to enter `plan-review`.
4. In `plan-review`, show the full plan and wait for an explicit approval.
   Revise and re-show it until approved. Only after a clear approval, run
   `state.py approve-plan <ticket-id>` and then `state.py advance <ticket-id>`.
   Never write code before those commands succeed.
5. In `implement`, confirm the target repository is clean, create a normal
   git branch or worktree, and record its branch with `state.py record-branch`.
   Implement the approved plan, keep commits narrowly scoped, and do not push
   until validation is complete. Run `state.py advance <ticket-id>` only after
   the code is ready to validate.
6. In `validate`, run each command named in the approved plan through
   `validate.py`; it records command, output, and result in the work-item
   folder without using a shell. Fix failures and rerun checks. Record
   `passed` only when every planned check succeeds. A failed check may be
   bypassed only after the developer explicitly accepts the risk; record that
   exact reason as `overridden`. Then advance to `pr`.
7. In `pr`, inspect the final diff, commit if needed, push the recorded branch,
   and create the pull request. Record the real URL with `state.py record-pr`,
   then advance to `done`. Set the brief's status to `pr_open`; when the local
   backlog database exists, run its `record-brief` command so later triage sees
   this work as in flight. Report the URL and validation result.

If code changes after validation, run `state.py invalidate-validation` before
continuing. The state helper will block the pull-request stage until validation
is recorded again.

## Example

`/develop-ticket 4211` reads the ready brief for invoice retries, writes an
approved plan, works on `ticket-4211`, records the repository's test commands
in `VALIDATION.md`, and opens a pull request. If the agent is interrupted, a
later `/develop-ticket 4211` reads the same brief, plan, validation log, and
current stage instead of relying on a prior chat session.

## Bundled resources

- `scripts/state.py` — **run** to initialise, inspect, and advance the ticket
  lifecycle. It is the only script allowed to change `state.json`.
- `scripts/validate.py` — **run** once for each planned validation command.
  Pass the command after `--`; it runs without a shell and appends a durable
  result to `VALIDATION.md`.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
