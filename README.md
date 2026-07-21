# Ticket Foreman

An agent-native ticket workflow with two explicit tasks, both implemented in
[`.agents/`](.agents/):

1. `/backlog-triage` turns selected backlog items into accepted Markdown work
   briefs. It does not touch code.
2. `/develop-ticket <ticket-id>` takes one ready brief through understanding,
   plan approval, implementation, validation, and a pull request.

The work brief is the boundary between the tasks. Local ticket details, plans,
validation output, and lifecycle state live in `.agents/work-items/` and are
not committed.

Open this repository in an agent-aware development environment and invoke the
first task when choosing work. Invoke the second only after the developer has
accepted a brief. See [`.agents/README.md`](.agents/README.md) for the layout.
