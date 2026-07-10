# AGENTS.md

## Project

This repository contains only the two agent-native ticket workflows in
`.agents/`. There is no application runtime, global skill installer, service
adapter, or headless session manager.

## Architecture

- `.agents/skills/backlog-triage/` owns intake, prioritisation, and accepted
  Markdown work briefs. Its SQLite database is a local read model for source
  facts and recorded decisions; it never changes target-repository code.
- `.agents/skills/develop-ticket/` owns one ready brief through plan approval,
  implementation, validation, and pull-request creation.
- `.agents/work-items/` is ignored local runtime state. It contains ticket
  details and may contain sensitive project information; never commit it.
- `BRIEF.md` is the only handoff between the two tasks. Keep it readable by a
  developer and an agent; do not introduce JSON response contracts.

## Conventions

- Keep every workflow asset under `.agents/`; do not introduce a second skill
  location or copy skills into a user-global directory.
- New helper scripts are self-contained PEP 723 `uv run --script` files.
- Use `pathlib` and argument lists for subprocesses. Do not use a shell in
  helper scripts.
- `state.py` is the only writer of a work item's `state.json`; never change a
  stage by editing the file.
- Preserve explicit plan approval and recorded validation before a pull request.
