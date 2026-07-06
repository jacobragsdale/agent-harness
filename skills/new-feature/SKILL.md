---
name: new-feature
description: Playbook for new-feature tickets in the ticket loop — scope tightly, follow existing patterns. Consult when interviewing, planning, or executing a feature ticket.
---

# New feature playbook

- Interview focus: the **boundary** of v1 (what's explicitly out), who
  consumes the feature and through what interface, backward compatibility,
  feature flag / rollout expectations, and any UI/API contract details the
  ticket hand-waves.
- Find the closest existing feature and mirror its structure, naming, and
  layering — consistency beats elegance in a brownfield repo.
- Plans must list new files and their responsibilities explicitly; "add
  supporting code" is not a plan.
- Prefer the smallest end-to-end slice that satisfies the ticket over a
  complete-but-unshippable framework.
- Surface data-model or config-schema changes prominently in the plan —
  they're the expensive-to-reverse part.
