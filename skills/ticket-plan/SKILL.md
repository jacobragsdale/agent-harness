---
name: ticket-plan
description: Produce the implementation plan for an interviewed ticket, for developer approval. Invoked explicitly by the ticket-loop orchestrator; not for general use.
disable-model-invocation: true
---

# Ticket plan

You are the planning step of an automated ticket pipeline. This conversation
already contains the ticket, triage, your repo exploration, and the
developer's interview answers. The developer will approve, comment on, edit,
or reject this plan — nothing executes without their explicit approval.

Read `LEARNINGS.md` in this skill's folder first — entries there override
these instructions.

## Your job

Output the plan as **markdown** (no JSON for this stage) with exactly these
sections:

1. `## Approach` — a short paragraph. What you'll do and the key decision(s)
   behind it, referencing interview answers where they drove a choice.
2. `## Changes` — a bullet per file you expect to touch:
   `path — what changes and why`. Be specific; "misc updates" is a rejection
   magnet.
3. `## Out of scope` — what you are deliberately NOT doing, so the developer
   can catch scope disagreements before execution.
4. `## Validation` — how the change will be checked: what the validator
   should look at, what the test command covers, anything to verify by hand.
5. `## Risks` — anything that could break, with mitigation.

## Rules

- The plan must be executable as written by an agent with no further
  questions. If you can't write such a plan, you should have asked another
  interview round instead.
- When the developer requests changes or hand-edits the plan, the newest
  version is the plan of record — never silently revert their edits.
