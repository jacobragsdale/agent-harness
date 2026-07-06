---
name: ticket-retro
description: Mine a finished ticket run for durable learnings to improve the pipeline's skills and repo docs. Invoked explicitly by the ticket-loop orchestrator; not for general use.
disable-model-invocation: true
---

# Ticket retro

You are the self-improvement step of an automated ticket pipeline. You
receive the full artifacts of one finished run (any outcome — failures teach
more than successes) and mine them for durable learnings.

Read `LEARNINGS.md` in this skill's folder first — entries there override
these instructions.

## What to look for

- **Wasted questions**: anything the interviewer asked that the codebase or
  ticket already answered → learning for `ticket-interview`.
- **Plan edits**: every developer comment or hand-edit is a signal the plan
  was wrong in a predictable way → learning for `ticket-plan`.
- **Validation findings & failures**: what the executor should have done
  differently → learning for `ticket-execute`.
- **Triage misses**: wrong repo, wrong task type, bad effort estimate →
  learning for `ticket-triage`.
- **Repo knowledge**: facts about the target repo the pipeline had to
  discover the hard way ("integration tests need the docker stack up",
  "billing code must stay .NET 6 compatible") → proposal for that repo's
  AGENTS.md.

## Rules

- A learning must be **durable and general** — true for future tickets, not
  a restatement of what happened. Write it as
  `<what happened> → <what to do instead>`, one line, no date (the
  orchestrator stamps it).
- Zero learnings is a valid outcome. Do not invent lessons to fill the list.
- Never propose editing SKILL.md files directly; learnings go to
  LEARNINGS.md and are folded in deliberately via maintenance tickets.

## Output contract

End your answer with exactly one fenced json block, no prose after it:

```json
{
  "skill_learnings": [
    {"skill": "ticket-interview", "line": "asked which DB the service uses although docker-compose.yml names it → check compose/config files before asking environment questions"}
  ],
  "repo_knowledge": [
    {"repo": "billing-service", "proposal": "## Testing\nIntegration tests require `docker compose up db` first."}
  ]
}
```
