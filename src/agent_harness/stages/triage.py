"""Triage: classify the ticket and map it to a target repo.

A short, read-only classification call in the orchestrator workspace. The
ticket's long-lived session starts at the interview, inside the target repo,
where the agent can actually look around.
"""

from __future__ import annotations

import json

from .. import ui
from ..config import registry_block
from ..context import LoopContext
from ..models import TicketState
from ..state import TicketWorkspace

TASK_TYPES = ("fix-bug", "new-feature", "prod-issue", "qa-test", "infra-maintenance")


def run_triage(ctx: LoopContext, ws: TicketWorkspace) -> dict:
    ui.stage(f"Triage — {ws.ticket.id}: {ws.ticket.title}")
    grooming = ws.read_artifact("grooming.json")
    grooming_block = f"\n\nGrooming notes (pre-triage recon):\n{grooming}" if grooming else ""
    prompt = (
        "/ticket-triage\n\n"
        f"{ws.ticket.summary_block()}{grooming_block}\n\n"
        f"Registered repos:\n{registry_block(ctx.repos)}\n\n"
        f"Valid task_type values: {', '.join(TASK_TYPES)}"
    )
    payload, _ = ctx.agent.run_json(prompt, mode="plan", workspace=ctx.settings.root)
    if not isinstance(payload, dict):
        raise ValueError(f"triage returned {type(payload).__name__}, expected object")

    ws.write_artifact("triage.json", json.dumps(payload, indent=2) + "\n")
    ws.set_field("repo", payload.get("repo"))
    ws.set_field("task_type", payload.get("task_type"))
    ws.transition(TicketState.TRIAGED)
    ctx.store.update_status(ws.ticket.id, "triaged", note=payload.get("summary", ""))

    ui.info(
        f"classified as [bold]{payload.get('task_type')}[/bold] in repo "
        f"[bold]{payload.get('repo')}[/bold] "
        f"(priority {payload.get('priority')}, effort {payload.get('effort')})"
    )
    return payload
