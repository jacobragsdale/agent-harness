"""PR babysitter: follow through on open PRs until they merge.

For each PR_OPEN ticket: poll PR status via the adapter. Merged → done;
closed → rejected; CI failure / review comments / conflict → the ticket's
own session (it wrote the code) drafts replies and fixes read-only, you
approve, then it applies with write access. Replies and pushes go through
the adapter (journaled by the mock).
"""

from __future__ import annotations

import json

from .. import ui
from ..adapters.prs import PRStatus
from ..context import LoopContext
from ..models import TicketState
from ..state import TicketWorkspace, append_metrics


def _events_block(status: PRStatus) -> str:
    parts = []
    if status.ci == "failing":
        parts.append(f"CI IS FAILING. Log excerpt:\n{status.ci_log or '(no log provided)'}")
    if status.merge_conflict:
        parts.append("The branch has a MERGE CONFLICT with its target.")
    for c in status.comments:
        location = f" ({c.get('path')}:{c.get('line')})" if c.get("path") else ""
        parts.append(
            f"REVIEW COMMENT id={c.get('id')} from {c.get('author', '?')}{location}:\n"
            f"{c.get('text', '')}"
        )
    return "\n\n".join(parts)


def _finish(ctx: LoopContext, ws: TicketWorkspace, state: TicketState, note: str) -> None:
    ws.transition(state)
    ctx.store.update_status(ws.ticket.id, str(state), note=note)
    append_metrics(
        ctx.settings.metrics_file,
        {"ticket": ws.ticket.id, "outcome": str(state), "via": "babysit", "note": note},
    )
    ui.info(f"[bold]{ws.ticket.id} → {state}[/bold] ({note})")


def run_babysit(ctx: LoopContext, ws: TicketWorkspace) -> None:
    pr_url = ws.get_field("pr_url") or ""
    branch = ws.get_field("worktree") or f"ticket-{ws.ticket.id}"
    status = ctx.prs.get_pr_status(pr_url, branch)

    if status.state == "merged":
        _finish(ctx, ws, TicketState.DONE, "PR merged")
        return
    if status.state == "closed":
        ws.set_field("rejection_reason", "PR closed without merge")
        _finish(ctx, ws, TicketState.REJECTED, "PR closed without merge")
        return
    if not status.has_events():
        ui.info(f"{ws.ticket.id}: PR quiet (ci={status.ci}, no comments)")
        return

    ui.stage(f"Babysit — {ws.ticket.id} ({pr_url})")
    events = _events_block(status)
    ui.show_markdown(events, title="PR events")

    worktree_path = ws.get_field("worktree_path")
    repo = ctx.repo(ws.get_field("repo"))
    workspace = worktree_path or repo.path

    # Draft phase: read-only, in the session that wrote the code.
    draft, result = ctx.agent.run_json(
        f"/pr-babysit\n\nEvents on the open PR for ticket {ws.ticket.id}:\n\n{events}",
        mode="plan",
        workspace=workspace,
        resume=ws.get_field("session_id"),
    )
    ws.set_field("session_id", result.session_id or ws.get_field("session_id"))
    if not isinstance(draft, dict):
        draft = {"summary": str(draft), "replies": [], "planned_changes": []}
    ws.append_artifact("babysit.jsonl", json.dumps({"events": events, "draft": draft}) + "\n")

    lines = [draft.get("summary", "")]
    for r in draft.get("replies", []):
        lines += ["", f"**reply to {r.get('comment_id')}:** {r.get('body')}"]
    if draft.get("planned_changes"):
        lines += ["", "**code changes:**"] + [f"- {c}" for c in draft["planned_changes"]]
    for n in draft.get("needs_developer", []):
        lines += ["", f"**needs you:** {n}"]
    ui.show_markdown("\n".join(lines), title="proposed response")

    if ui.choice({"a": "approve & apply", "s": "skip for now"}) != "a":
        ui.info("skipped — PR left as-is")
        return

    if draft.get("planned_changes"):
        apply_result = ctx.agent.run(
            "Apply the planned changes you just drafted for the PR events, commit them "
            "(never push), and end with the apply-phase json from /pr-babysit.",
            force=True,
            workspace=workspace,
            resume=ws.get_field("session_id"),
        )
        ws.set_field("session_id", apply_result.session_id or ws.get_field("session_id"))
        ctx.prs.push_branch(repo.name, branch)
        ui.info("changes applied, committed, and push recorded")
    for r in draft.get("replies", []):
        ctx.prs.post_reply(pr_url, r.get("comment_id", ""), r.get("body", ""))
    if draft.get("replies"):
        ui.info(f"{len(draft['replies'])} repl(ies) recorded")
    ctx.store.add_comment(ws.ticket.id, f"[babysit] {draft.get('summary', '')}")
