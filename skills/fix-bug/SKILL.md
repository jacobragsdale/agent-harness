---
name: fix-bug
description: Playbook for bug-fix tickets in the ticket loop — reproduce first, find the root cause, fix minimally. Consult when interviewing, planning, or executing a bug ticket.
---

# Bug fix playbook

- **Reproduce before you plan.** Find the code path that produces the
  reported behavior and be able to explain the mechanism. A fix without an
  understood root cause is a guess.
- Interview focus: exact reproduction conditions, affected
  versions/environments, whether bad data already exists that the fix must
  also repair, what "fixed" means to the reporter.
- Fix at the root cause, minimally. Don't refactor around the bug — file
  that as an observation for the retro instead.
- Look for sibling occurrences: the same mistake pattern often exists in
  neighboring code. Mention them in the plan even if out of scope.
- If tests exist near the bug, add/adjust one that fails before the fix and
  passes after. If none exist, say so in the plan's Validation section
  rather than inventing a test framework.
