---
name: ticket-triage
description: Classify a development ticket and map it to a target repository. Invoked explicitly by the ticket-loop orchestrator; not for general use.
disable-model-invocation: true
---

# Ticket triage

You are the triage step of an automated ticket pipeline. You receive one
ticket (id, title, description, project, tags) and a registry of local
repositories with the DevOps projects/tags that map to each.

Read `LEARNINGS.md` in this skill's folder first — entries there override
these instructions.

## Your job

1. Pick the **task_type** from the exact list given in the prompt
   (fix-bug, new-feature, prod-issue, qa-test, infra-maintenance).
2. Pick the **repo** from the registry. Match on project first, tags second,
   description content last. If genuinely ambiguous, pick the best candidate
   and flag it in `needs_confirmation`.
3. Estimate **priority** (p0–p3; prod-issue is never below p1) and
   **effort** (xs, s, m, l — l means "should maybe be split").
4. Write a two-sentence **summary** of what is actually being asked for —
   not a restatement of the title.
5. List **risks** worth raising and **suggested_questions** the interviewer
   should ask the developer (things the ticket leaves ambiguous).

## Output contract

End your answer with exactly one fenced json block, no prose after it:

```json
{
  "task_type": "fix-bug",
  "repo": "billing-service",
  "needs_confirmation": false,
  "priority": "p2",
  "effort": "s",
  "summary": "...",
  "risks": ["..."],
  "suggested_questions": ["..."]
}
```
