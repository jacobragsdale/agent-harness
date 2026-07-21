# Ticket Foreman Workflows

All workflow behaviour lives in this folder.

- `skills/backlog-triage/` prepares accepted Markdown work briefs.
- `skills/backlog-triage/resources/` contains the tracked SQLite schema,
  Azure DevOps field contract, and named triage queries.
- `skills/develop-ticket/` implements one accepted brief through a small,
  gated lifecycle.
- `work-items/` is local runtime state. It holds briefs, plans, validation
  logs, lifecycle state, and the ignored `backlog.sqlite3` read model; it is
  intentionally ignored by git.

The skills are explicit: start with `/backlog-triage`, then run
`/develop-ticket <ticket-id>` for one ready brief.
