"""The loop driver: dispatch each ticket to its next stage until terminal.

Resumable by construction — the dispatcher reads the persisted status, so an
interrupted run picks every ticket up exactly where it left off.
"""

from __future__ import annotations

from . import ui
from .context import LoopContext
from .cursor import AgentError
from .models import TERMINAL_STATES, Ticket, TicketState
from .stages.execute import run_execute
from .stages.interview import run_interview
from .stages.plan import run_plan_gate
from .stages.retro import run_retro
from .stages.triage import run_triage
from .stages.validate import run_validate
from .state import TicketWorkspace, append_metrics


def _pr_gate(ctx: LoopContext, ws: TicketWorkspace) -> None:
    validation = ws.read_artifact("validation.md")
    if validation:
        ui.show_markdown(validation, title="validation findings (advisory)")
    if not ui.confirm(f"Open PR for ticket {ws.ticket.id}?"):
        ws.set_field("rejection_reason", "declined at PR gate")
        ws.transition(TicketState.REJECTED)
        ctx.store.update_status(ws.ticket.id, "rejected", note="declined at PR gate")
        return

    repo = ctx.repo(ws.get_field("repo"))
    branch = ws.get_field("worktree") or f"ticket-{ws.ticket.id}"
    pr = ctx.prs.create_pr(
        repo_name=repo.name,
        source_branch=branch,
        target_branch=repo.default_branch,
        title=f"{ws.ticket.id}: {ws.ticket.title}",
        body=ws.latest_plan() or ws.ticket.description,
    )
    ws.set_field("pr_url", pr.url)
    ws.transition(TicketState.PR_OPEN)
    ctx.store.update_status(ws.ticket.id, "pr_open", note=pr.url)
    ctx.store.add_comment(ws.ticket.id, f"PR opened: {pr.url}")
    ui.info(f"PR recorded: {pr.url}")
    ws.transition(TicketState.DONE)
    ctx.store.update_status(ws.ticket.id, "done")


def run_ticket(ctx: LoopContext, ticket: Ticket) -> TicketState:
    ws = TicketWorkspace.open(ctx.settings.tickets_dir, ticket)
    if ws.status in TERMINAL_STATES:
        ui.info(f"{ticket.id} already {ws.status} — skipping")
        return ws.status

    try:
        while ws.status not in TERMINAL_STATES:
            status = ws.status
            if status == TicketState.NEW:
                run_triage(ctx, ws)
            elif status == TicketState.TRIAGED:
                run_interview(ctx, ws)
            elif status == TicketState.INTERVIEWING or status == TicketState.AWAITING_APPROVAL:
                run_plan_gate(ctx, ws)
            elif status == TicketState.APPROVED:
                run_execute(ctx, ws)
            elif status == TicketState.EXECUTING:
                # Interrupted mid-execution on a previous run; re-drive it.
                run_execute(ctx, ws)
            elif status == TicketState.VALIDATING:
                run_validate(ctx, ws)
                _pr_gate(ctx, ws)
            elif status == TicketState.PR_OPEN:
                ws.transition(TicketState.DONE)
                ctx.store.update_status(ticket.id, "done")
    except Exception as e:
        # Any stage failure (agent error, unknown repo from triage, missing
        # worktree, test-command timeout) fails THIS ticket, not the loop.
        # KeyboardInterrupt is not caught: state is persisted, rerun resumes.
        ui.info(f"[red]failure on {ticket.id}: {e}[/red]")
        ws.set_field("failure", str(e))
        if ws.status not in TERMINAL_STATES:
            ws.transition(TicketState.FAILED)
        ctx.store.update_status(ticket.id, "failed", note=str(e)[:500])

    # Retro runs for every terminal outcome; its own failure must not mask one.
    try:
        run_retro(ctx, ws)
    except AgentError as e:
        ui.info(f"[yellow]retro skipped ({e})[/yellow]")

    append_metrics(
        ctx.settings.metrics_file,
        {
            "ticket": ticket.id,
            "outcome": ws.status,
            "interview_rounds": ws.get_field("interview_rounds"),
            "plan_versions": ws.next_plan_version() - 1,
            "pr_url": ws.get_field("pr_url"),
        },
    )
    return ws.status


def run_loop(ctx: LoopContext, only_ticket: str | None = None, max_tickets: int = 0) -> None:
    tickets = ctx.store.fetch_tickets()
    if only_ticket:
        tickets = [t for t in tickets if t.id == only_ticket]
        if not tickets:
            raise SystemExit(f"ticket {only_ticket!r} not found in the tickets file")
    handled = 0
    for ticket in tickets:
        ws = TicketWorkspace.open(ctx.settings.tickets_dir, ticket)
        if ws.status in TERMINAL_STATES:
            continue
        outcome = run_ticket(ctx, ticket)
        handled += 1
        ui.info(f"[bold]{ticket.id} → {outcome}[/bold]")
        if max_tickets and handled >= max_tickets:
            break
    if handled == 0:
        ui.info("nothing to do — all tickets are in terminal states")
