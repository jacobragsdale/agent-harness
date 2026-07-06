---
name: prod-issue
description: Playbook for production-incident tickets in the ticket loop — stabilize first, smallest safe change. Consult when interviewing, planning, or executing a prod issue.
---

# Production issue playbook

- Interview focus: current impact and blast radius, whether a
  mitigation/rollback already happened, error messages/logs the developer
  can paste, and the deadline pressure (hotfix branch vs normal flow).
- Bias to the **smallest change that stops the bleeding**. Root-cause
  cleanup becomes a follow-up ticket, noted in the plan's Out-of-scope.
- The plan must separate *mitigation* from *fix* if they differ, and state
  the rollback story for the change itself.
- Be paranoid in execution: no drive-by changes, no dependency bumps, no
  refactors — the diff should be reviewable in one screen if possible.
- Validation focus: how we'll know it worked in prod (log line, metric,
  query), not just that tests pass.
