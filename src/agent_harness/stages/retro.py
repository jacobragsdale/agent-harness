"""Retro: mine the run for learnings. Runs after every terminal state.

Two routing rules (agreed design):
- workflow knowledge → AUTO-APPENDED as dated lines to the relevant skill's
  LEARNINGS.md in this repo (house convention), then skills re-sync;
- repo knowledge → shown as a proposal; only applied (appended to the
  worktree's AGENTS.md, riding the ticket's branch) if you approve.

When a LEARNINGS.md grows past FOLD_THRESHOLD entries we flag that a
fold-into-SKILL.md maintenance ticket is due (auto-filing one through the
pipeline itself is a TODO — see TODO.md).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .. import ui
from ..context import LoopContext
from ..skills_sync import sync_skills
from ..state import TicketWorkspace

FOLD_THRESHOLD = 8


def _append_learning(skills_dir: Path, skill: str, line: str) -> bool:
    learnings = skills_dir / skill / "LEARNINGS.md"
    if not learnings.exists():
        return False
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    with learnings.open("a", encoding="utf-8") as f:
        f.write(f"- {today}: {line}\n")
    return True


def _entry_count(skills_dir: Path, skill: str) -> int:
    learnings = skills_dir / skill / "LEARNINGS.md"
    if not learnings.exists():
        return 0
    return sum(
        1 for line in learnings.read_text(encoding="utf-8").splitlines() if line.startswith("- 2")
    )


def _gather_artifacts(ws: TicketWorkspace) -> str:
    parts = [ws.ticket.summary_block(), f"\nFinal status: {ws.status}"]
    for name in ("triage.json", "interview.md", "validation.md", "execute-report.json"):
        content = ws.read_artifact(name)
        if content:
            parts.append(f"\n--- {name} ---\n{content[:6000]}")
    plans = sorted(ws.dir.glob("plan-v*.md"))
    parts.append(f"\nPlan went through {len(plans)} revision(s).")
    if len(plans) > 1:
        parts.append(f"--- final plan ---\n{plans[-1].read_text(encoding='utf-8')[:4000]}")
    reason = ws.get_field("rejection_reason")
    if reason:
        parts.append(f"\nDeveloper's rejection reason: {reason}")
    return "\n".join(parts)


def run_retro(ctx: LoopContext, ws: TicketWorkspace) -> dict:
    ui.stage(f"Retro — {ws.ticket.id}")
    prompt = (
        "/ticket-retro\n\n"
        "Run artifacts follow. Mine them for durable learnings.\n\n"
        f"{_gather_artifacts(ws)}"
    )
    # Fresh session, orchestrator workspace (it is proposing skill edits).
    payload, _ = ctx.agent.run_json(prompt, mode="plan", workspace=ctx.settings.root)
    if not isinstance(payload, dict):
        payload = {}
    ws.write_artifact("retro.json", json.dumps(payload, indent=2) + "\n")

    # 1. Workflow learnings: auto-append.
    appended = 0
    for item in payload.get("skill_learnings", []):
        skill, line = item.get("skill", ""), item.get("line", "")
        if skill and line and _append_learning(ctx.settings.skills_dir, skill, line):
            appended += 1
            ui.info(f"learning → skills/{skill}/LEARNINGS.md: {line[:100]}")
            if _entry_count(ctx.settings.skills_dir, skill) >= FOLD_THRESHOLD:
                ui.info(
                    f"[yellow]skills/{skill}/LEARNINGS.md has ≥{FOLD_THRESHOLD} entries — "
                    "consider a fold-into-SKILL.md maintenance ticket[/yellow]"
                )
    if appended:
        sync_skills(ctx.settings.skills_dir)
        ui.info(f"{appended} learning(s) recorded; skills re-synced")

    # 2. Repo knowledge: gated.
    for proposal in payload.get("repo_knowledge", []):
        text = proposal.get("proposal", "")
        if not text:
            continue
        ui.show_markdown(text, title="proposed addition to the target repo's AGENTS.md")
        worktree = ws.get_field("worktree_path")
        if worktree and Path(worktree).exists():
            if ui.confirm("Apply to the worktree's AGENTS.md (rides this ticket's branch)?"):
                agents_md = Path(worktree) / "AGENTS.md"
                with agents_md.open("a", encoding="utf-8") as f:
                    f.write(f"\n{text}\n")
                ui.info("appended to worktree AGENTS.md")
        else:
            ui.info("no live worktree — proposal recorded in retro.json only")

    return payload
