# Agent Harness Workflows

All workflow behaviour lives in this folder.

- `skills/backlog-triage/` prepares accepted Markdown work briefs.
- `skills/develop-ticket/` implements one accepted brief through a small,
  gated lifecycle.
- `work-items/` is local runtime state. It holds briefs, plans, validation
  logs, and lifecycle state; it is intentionally ignored by git.

The skills are explicit: start with `/backlog-triage`, then run
`/develop-ticket <ticket-id>` for one ready brief.
