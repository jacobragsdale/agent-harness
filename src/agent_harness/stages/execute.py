"""Execute: the approved plan, with write access, in an isolated worktree.

Same session as interview/plan (--resume), now with --force. The Cursor CLI
manages the worktree (`-w ticket-<id> --worktree-base <branch>`). The agent
may commit but must not push — pushing and PRs are the orchestrator's job
(and are mocked in the demo).
"""

from __future__ import annotations

import json

from .. import ui
from ..context import LoopContext
from ..cursor import extract_json_payload
from ..models import TicketState
from ..state import TicketWorkspace


def run_execute(ctx: LoopContext, ws: TicketWorkspace) -> dict:
    ui.stage(f"Execute — {ws.ticket.id}")
    repo = ctx.repo(ws.get_field("repo"))
    worktree = f"ticket-{ws.ticket.id}"

    if ws.status == TicketState.APPROVED:
        ws.transition(TicketState.EXECUTING)
        ctx.store.update_status(ws.ticket.id, "in_progress")
    ws.set_field("worktree", worktree)

    prompt = (
        "/ticket-execute\n\n"
        "Execute the approved plan of record from this conversation. "
        f"Work only inside this worktree. Branch/worktree name: {worktree}."
    )
    result = ctx.agent.run_streaming(
        prompt,
        transcript_path=ws.dir / "execute.stream.jsonl",
        on_event=ui.narrate_stream_event,
        force=True,
        resume=ws.get_field("session_id"),
        workspace=repo.path,
        worktree=worktree,
        worktree_base=repo.default_branch,
    )
    ws.set_field("session_id", result.session_id or ws.get_field("session_id"))

    try:
        report = extract_json_payload(result.text)
        if not isinstance(report, dict):
            report = {"summary": result.text}
    except json.JSONDecodeError:
        report = {"summary": result.text}
    ws.write_artifact("execute-report.json", json.dumps(report, indent=2) + "\n")
    if report.get("worktree_path"):
        ws.set_field("worktree_path", report["worktree_path"])

    ws.transition(TicketState.VALIDATING)
    ui.info(f"execution finished: {report.get('summary', '(no summary)')[:200]}")
    return report
