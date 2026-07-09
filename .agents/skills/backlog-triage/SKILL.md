---
name: backlog-triage
description: "Use when the developer asks to triage, groom, rank, choose, or prepare a backlog of tickets for implementation. Produces accepted Markdown work briefs only; it does not plan, edit code, or open pull requests."
disable-model-invocation: true
---

# Backlog triage

Turn a backlog into a small set of accepted, implementation-ready work briefs.
This is an intake task, not a development task: make prioritisation and scope
decisions visible to the developer, then create a brief only for work they
accept. Do not edit a target repository, create a branch, or open a pull
request.

## When to use

Run this skill explicitly for requests such as:

- `/backlog-triage`
- “Which tickets should I work next?”
- “Clean up this backlog and prepare the next few items.”

Do not use it to implement one ticket, respond to a pull-request comment, or
write code. Hand those requests to `/develop-ticket` after a work brief exists.

## Workflow

1. Read existing briefs with `uv run .agents/skills/backlog-triage/scripts/brief.py list`.
   Treat an existing ready brief as in-flight context; do not nominate it again
   unless the developer asks to revisit it.
2. Read the backlog from the source the developer supplied. Prefer its primary
   ticket system or export over summaries. Extract the ticket ID, source link,
   title, description, acceptance criteria, current state, and any priority or
   age signals.
3. Do the judgment work in one pass: identify duplicates, stale items, missing
   information, likely target repository, dependencies, urgency, and a
   recommended small batch. Do not inspect code or design an implementation.
4. Show the developer a short ranked recommendation. For every proposed item,
   give the ticket ID, title, target repository, one-line rationale, and any
   unresolved decision. Ask them which items to accept, defer, reject, or split.
   Never create briefs or change remote tickets before that answer.
5. For each accepted item, run `brief.py init` to create
   `.agents/work-items/<ticket-id>/BRIEF.md`. Use `--description-file` for a
   long ticket body and `--description` for short text. The script creates the
   durable Markdown shape; edit the empty triage fields in place afterward.
   For example: `uv run .agents/skills/backlog-triage/scripts/brief.py init --id <id> --title <title> --source <source> --repo <repo-and-path> --description-file <file>`.
6. Complete every field below, change `Status` to `ready`, and show the brief
   back to the developer:

   - target repository and its local path
   - why the work matters now
   - testable acceptance criteria
   - explicit constraints and out-of-scope work
   - dependencies, risks, and genuinely unresolved questions

7. End with the ready ticket IDs and the exact next invocation:
   `/develop-ticket <ticket-id>`. Do not start development in this task.

## Example

Input: ticket `4211`, “Retry failed invoice posts”, from the billing backlog.

After the developer accepts it, create `4211/BRIEF.md`, fill its target
repository, acceptance criteria (retry transient failures, cap attempts, retain
the original error), and mark it `ready`. Finish with:

> Ready: 4211 — run `/develop-ticket 4211` when you want to implement it.

## Bundled resources

- `scripts/brief.py` — **run** to initialise, list, or display the canonical
  Markdown work briefs. It owns only file layout and never makes triage
  decisions.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
