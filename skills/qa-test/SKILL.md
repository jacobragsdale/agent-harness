---
name: qa-test
description: Playbook for QA/testing tickets in the ticket loop — verify behavior, write repeatable checks. Consult when interviewing, planning, or executing a QA ticket.
---

# QA / testing playbook

- Interview focus: what "verified" means (manual checklist vs automated
  suite), which environments/configs matter, known-flaky areas to avoid
  blocking on, and where results should be recorded.
- Start from the acceptance criteria; turn each into a concrete, repeatable
  check. Note criteria that are untestable as written — that's a finding,
  not a blocker.
- This codebase has weak test coverage: prefer adding a few durable,
  low-maintenance tests around the ticket's area over broad brittle suites.
- Keep test data/fixtures self-contained; a test that needs an undocumented
  local setup will never be run again.
- Report format matters: the ticket's outcome is the evidence (what was
  checked, how, result), not just green checkmarks.
