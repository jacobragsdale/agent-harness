---
name: infra-maintenance
description: Playbook for infrastructure/maintenance tickets in the ticket loop — upgrades, config, CI, dependencies. Consult when interviewing, planning, or executing infra work.
---

# Infra / maintenance playbook

- Interview focus: maintenance window/urgency, environments in scope (dev
  only? prod?), rollback expectations, and whether secrets/credentials are
  involved (if so, the plan must say who provides them — never invent or
  commit secrets).
- Dependency/tool upgrades: read the changelog between versions; list the
  breaking changes that apply to this repo in the plan. Pin exact versions.
- Config changes: show before/after in the plan. Anything environment-
  specific goes through the repo's established config mechanism, not
  hardcoding.
- Execution must be reversible: one logical change per commit so a partial
  rollback is possible.
- Validation focus: the system still builds/starts/deploys — run the
  heaviest check the repo offers locally (build, container image, CI
  script) before declaring success.
