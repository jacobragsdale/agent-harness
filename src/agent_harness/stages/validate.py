"""Validate: fresh-eyes review of the diff, plus the repo's test command.

Deliberately shallow (v1): a NEW session — no memory of writing the code —
reads the diff against the ticket's intent, and the orchestrator runs the
configured test command deterministically. Findings never block; they're
shown at the PR gate for the developer to weigh.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .. import ui
from ..context import LoopContext
from ..state import TicketWorkspace


def _worktree_path(ctx: LoopContext, ws: TicketWorkspace) -> Path:
    reported = ws.get_field("worktree_path")
    if reported and Path(reported).exists():
        return Path(reported)
    # Documented Cursor CLI layout: ~/.cursor/worktrees/<repo>/<name>
    repo = ctx.repo(ws.get_field("repo"))
    fallback = Path.home() / ".cursor" / "worktrees" / repo.path.name / ws.get_field("worktree")
    if fallback.exists():
        return fallback
    raise FileNotFoundError(
        f"cannot locate worktree for {ws.ticket.id}; agent reported {reported!r}"
    )


def _run_tests(ctx: LoopContext, ws: TicketWorkspace, worktree: Path) -> str:
    repo = ctx.repo(ws.get_field("repo"))
    if not repo.test_command:
        return "no test command configured for this repo"
    ui.info(f"running test command: {repo.test_command}")
    proc = subprocess.run(
        repo.test_command, shell=True, cwd=worktree, capture_output=True, text=True, timeout=1200
    )
    tail = (proc.stdout + proc.stderr)[-3000:]
    return f"exit code {proc.returncode}\n{tail}"


def run_validate(ctx: LoopContext, ws: TicketWorkspace) -> dict:
    ui.stage(f"Validate — {ws.ticket.id} (fresh eyes)")
    worktree = _worktree_path(ctx, ws)
    test_output = _run_tests(ctx, ws, worktree)

    plan = ws.latest_plan() or "(no plan artifact)"
    prompt = (
        "/ticket-validate\n\n"
        f"{ws.ticket.summary_block()}\n\n"
        f"The approved plan was:\n{plan}\n\n"
        f"Test command result:\n{test_output}\n\n"
        "Run `git diff` and `git log` in this worktree to see what was changed. "
        "You did NOT write this code. Judge it against the ticket and plan."
    )
    # Fresh session on purpose: no resume.
    payload, _ = ctx.agent.run_json(prompt, mode="plan", workspace=worktree)
    if not isinstance(payload, dict):
        payload = {"verdict": "concerns", "findings": [str(payload)]}
    payload["test_output"] = test_output

    findings = payload.get("findings", [])
    lines = [
        f"# Validation — ticket {ws.ticket.id}",
        "",
        f"Verdict: **{payload.get('verdict')}**",
        "",
    ]
    lines += [f"- {f}" for f in findings] or ["(no findings)"]
    lines += ["", "## Test command", "", "```", test_output, "```"]
    ws.write_artifact("validation.md", "\n".join(lines) + "\n")
    ws.write_artifact("validation.json", json.dumps(payload, indent=2) + "\n")

    ui.info(f"verdict: {payload.get('verdict')} ({len(findings)} finding(s))")
    return payload
