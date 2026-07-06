"""Plan gate: the agent proposes, you approve / comment / edit / reject / defer.

Unlimited comment cycles; every revision is preserved as plan-vN.md for the
retro stage to mine.
"""

from __future__ import annotations

from .. import ui
from ..context import LoopContext
from ..models import TicketState
from ..state import TicketWorkspace


def _request_plan(ctx: LoopContext, ws: TicketWorkspace, prompt: str) -> str:
    repo = ctx.repo(ws.get_field("repo"))
    result = ctx.agent.run(
        prompt, mode="plan", workspace=repo.path, resume=ws.get_field("session_id")
    )
    ws.set_field("session_id", result.session_id or ws.get_field("session_id"))
    version = ws.next_plan_version()
    ws.write_artifact(f"plan-v{version}.md", result.text)
    return result.text


def run_plan_gate(ctx: LoopContext, ws: TicketWorkspace) -> str:
    """Returns the terminal action: approve | reject | defer."""
    ui.stage(f"Plan — {ws.ticket.id}")

    plan = ws.latest_plan()
    if plan is None:
        plan = _request_plan(ctx, ws, "/ticket-plan\n\nProduce the implementation plan now.")
    if ws.status == TicketState.INTERVIEWING:
        ws.transition(TicketState.AWAITING_APPROVAL)
        ctx.store.update_status(ws.ticket.id, "awaiting_approval")

    while True:
        ui.show_markdown(plan, title=f"plan v{ws.next_plan_version() - 1}")
        action, detail = ui.plan_gate()

        if action == "approve":
            ws.transition(TicketState.APPROVED)
            ctx.store.update_status(ws.ticket.id, "approved")
            return "approve"

        if action == "comment":
            ui.info("sending your change request back to the agent...")
            plan = _request_plan(
                ctx,
                ws,
                "The developer reviewed the plan and requests changes:\n"
                f"{detail}\n\nRevise the plan. Output the full revised plan.",
            )

        elif action == "edit":
            edited = ui.edit_in_editor(plan)
            if edited.strip() and edited != plan:
                version = ws.next_plan_version()
                ws.write_artifact(f"plan-v{version}.md", edited)
                # Put the edited plan in the session's context so execution
                # follows the developer's version, not the agent's.
                repo = ctx.repo(ws.get_field("repo"))
                result = ctx.agent.run(
                    "The developer hand-edited the plan. This edited version is now the plan "
                    f"of record — follow it exactly when executing:\n\n{edited}\n\n"
                    "Acknowledge briefly.",
                    mode="plan",
                    workspace=repo.path,
                    resume=ws.get_field("session_id"),
                )
                ws.set_field("session_id", result.session_id or ws.get_field("session_id"))
                plan = edited
            else:
                ui.info("no changes made in editor")

        elif action == "reject":
            ws.set_field("rejection_reason", detail)
            ws.transition(TicketState.REJECTED)
            ctx.store.update_status(ws.ticket.id, "rejected", note=detail)
            return "reject"

        elif action == "defer":
            ws.transition(TicketState.DEFERRED)
            ctx.store.update_status(ws.ticket.id, "deferred")
            return "defer"
