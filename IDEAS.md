# IDEAS — high-impact future enhancements

The roadmap beyond [TODO.md](TODO.md) (which is near-term integration work).
Each idea says what it is, why it's high-leverage, and how it plugs into the
existing architecture. The recurring theme: **most of these produce
tickets**, so they feed the pipeline that already exists instead of needing
new machinery. The second theme: the loop already journals everything
(`journal.jsonl`, `metrics.jsonl`, ticket folders), and several ideas are
just *reading* that exhaust.

## 1. Daily digest / standup writer

**What:** A `loop digest` command (and eventually a scheduled morning run)
that reads journal + metrics + ticket states and writes the standup for you:
shipped yesterday, PRs awaiting review/events, blocked tickets with reasons,
patrol findings, learnings recorded.

**Why high-impact:** Nearly free to build (no new agent stages — one
summarization call over data we already have) and it's the feature that
makes the loop feel like a colleague. Also the natural home for "what needs
your attention" triage of the loop itself.

**Plugs in:** pure read of existing artifacts; optionally posts to the
ticket store as a comment or to chat via a new adapter.

## 2. Graduated autonomy (trust levels per task class)

**What:** Let ticket classes *earn* reduced gating. The approval history is
already recorded (plan versions, comment cycles, rejections, validation
verdicts per task_type × repo × effort). When a class hits a threshold —
e.g. ten consecutive `xs`/`s` infra tickets approved with zero plan edits —
offer: "auto-approve this class; plans still posted, you have a veto
window." Prod issues and anything `l` never qualify.

**Why high-impact:** This is the difference between a tool you babysit and
a junior developer you manage by exception. It's also honest: autonomy is
granted from measured performance, revocable on the first rejection.

**Plugs in:** a policy table computed from `metrics.jsonl`; the plan gate
consults it; every auto-approval is loudly journaled.

## 3. Incident intake (self-filing prod tickets)

**What:** A monitor adapter (App Insights / Sentry / log queries) plus a
scheduled pass: new alert → agent gathers evidence (stack trace, recent
deploys touching the code path, blast radius guess) → files an enriched
prod-issue ticket, deduped against open ones.

**Why high-impact:** Removes the worst-latency human step (noticing +
initial diagnosis) from the highest-urgency work. The prod-issue playbook
and grooming stage then apply as-is.

**Plugs in:** new `AlertSource` adapter protocol (mock = a JSON file, same
pattern as `pr-inbox.json`); output is tickets in the store.

## 4. Dependency & CVE patrol

**What:** Scheduled per-repo scan (outdated packages, CVE feeds, EOL
runtimes). For each finding worth acting on, file an infra-maintenance
ticket *with the changelog analysis already done* — the grooming enrichment
pre-baked.

**Why high-impact:** This is classic important-never-urgent work that rots
by default; the loop's whole value proposition is doing exactly this class
of work without occupying developer attention until the approval gate.

**Plugs in:** a `loop patrol deps` command; tickets into the store; the
existing infra-maintenance playbook executes them.

## 5. Test accretion patrol

**What:** Weekly pass per repo: find recently-merged changes with no test
coverage, write 2–3 durable tests around the hottest ones, open a small PR.
Deliberately slow drip, not a coverage crusade.

**Why high-impact:** The validator is shallow *because* the repos have weak
tests (deliberate v1 decision — see DESIGN.md). This patrol compounds:
every drip makes the validate stage stronger, which makes higher autonomy
(idea 2) safer. It's the loop improving its own safety net.

**Plugs in:** self-filed qa-test tickets through the normal pipeline —
interview and all, so you control what gets tested.

## 6. Docs-drift patrol + runbook maintenance

**What:** After merges (or weekly), diff reality against README/AGENTS.md/
runbooks in each registered repo: stale commands, renamed modules, removed
env vars. Small fixes become one-click PRs; structural drift becomes a
ticket.

**Why high-impact:** Docs drift is what makes *agents* worse over time —
AGENTS.md is load-bearing context for every future run. This is the
repo-knowledge half of the retro generalized beyond single tickets.

**Plugs in:** reuses the retro stage's gated AGENTS.md-proposal mechanic.

## 7. Batch interviews + parallel execution

**What:** Interview several tickets back-to-back in one morning block
(grooming already orders them), then execute the approved plans
concurrently — each ticket already has its own worktree, session, and state
folder. The plan gates and PR gates queue up as work completes.

**Why high-impact:** Converts the developer's day from interleaved
interruptions into two focused blocks (morning interviews, evening
reviews), with agent throughput no longer serialized on you.

**Plugs in:** the state machine already supports it; needs a worker pool
around `run_execute` and a queue for gates. The interview stays serial —
that's the human bottleneck by design.

## 8. Release notes & changelog writer

**What:** On a tag or on demand: collect merged PRs since the last release
(they all trace to tickets with plans and summaries), write stakeholder
release notes + technical changelog, open the release PR.

**Why high-impact:** The loop has *better* provenance than a human here —
every change links to a ticket, an approved plan, and a validation verdict.
Cheap to build; very visible output.

**Plugs in:** reads the journal + ticket folders; one writing stage; ships
through the existing PR adapter.

## Sequencing suggestion

Digest (1) first — trivial and immediately motivating. Then deps patrol (4)
as the first self-filing producer (it exercises ticket-creation plumbing
that incident intake (3) also needs). Graduated autonomy (2) once
`metrics.jsonl` has enough history to be meaningful. Test accretion (5)
before deepening the validator. (7) when single-ticket flow feels smooth.
