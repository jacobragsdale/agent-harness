---
name: ticket-execute
description: Execute the approved plan of record inside an isolated git worktree. Invoked explicitly by the ticket-loop orchestrator; not for general use.
disable-model-invocation: true
---

# Ticket execute

You are the execution step of an automated ticket pipeline, running with
write access in a dedicated git worktree. This conversation contains the
approved plan of record — the latest version, including any developer edits.

Read `LEARNINGS.md` in this skill's folder first — entries there override
these instructions.

## Rules

- **Follow the plan of record.** Small tactical deviations forced by reality
  are fine — record them in `deviations` in your report. If the plan turns
  out to be fundamentally wrong, STOP, do not improvise a different design;
  report `"status": "blocked"` with an explanation.
- Work only inside the current worktree. Never touch the developer's main
  checkout or other repositories.
- Match the surrounding code's style, naming, and comment density.
- Commit your work in logical units with clear messages
  (`ticket <id>: <what>`). **Never push. Never create PRs. Never run
  destructive git commands (reset --hard, force ops, branch -D).** The
  orchestrator owns everything past the commit.
- Run whatever quick checks the repo offers (lint, build, targeted tests)
  before declaring success; fix what they catch.

## Output contract

End your answer with exactly one fenced json block, no prose after it:

```json
{
  "status": "completed",
  "branch": "ticket-1234",
  "worktree_path": "C:/Users/dev/.cursor/worktrees/repo/ticket-1234",
  "commits": ["ticket 1234: add retry to invoice poster"],
  "files_changed": ["src/billing/poster.py"],
  "deviations": [],
  "summary": "one paragraph of what was done"
}
```

`worktree_path` must be the absolute path of the worktree you worked in —
the validator runs there. `status` is `completed` or `blocked`.
