"""Backlog grooming: the interactive pass over raw tickets, before triage.

Runs at the start of `loop run` (and via `loop groom`). One read-only agent
call per new ticket enriches it — likely repo, suspected files, duplicate
check against the rest of the backlog, split suggestions — then you decide
what happens to it. Downstream stages consume grooming.json.
"""

from __future__ import annotations

import json

from .. import ui
from ..config import registry_block
from ..context import LoopContext
from ..models import Ticket, TicketState
from ..state import TicketWorkspace


def _backlog_digest(all_tickets: list[Ticket], current_id: str) -> str:
    lines = [f"- {t.id} [{t.status or 'New'}] {t.title}" for t in all_tickets if t.id != current_id]
    return "\n".join(lines) or "(no other tickets)"


def _render(payload: dict) -> str:
    files = (
        "\n".join(f"  - `{f}`" for f in payload.get("suspected_files", [])) or "  - (none found)"
    )
    split = "\n".join(f"  - {s}" for s in payload.get("split_suggestion", []))
    parts = [
        payload.get("enrichment_summary", "(no summary)"),
        "",
        f"**Repo guess:** {payload.get('repo_guess')} · "
        f"**priority** {payload.get('priority_suggestion')} · "
        f"**effort** {payload.get('effort_suggestion')}",
        "",
        "**Suspected files:**",
        files,
        "",
        f"**Reproduction:** {payload.get('reproduction', {}).get('notes', '(not attempted)')}",
    ]
    if payload.get("duplicate_of"):
        parts += ["", f"**Possible duplicate of ticket {payload['duplicate_of']}**"]
    if split:
        parts += ["", "**Split suggestion:**", split]
    return "\n".join(parts)


def run_groom(ctx: LoopContext, ws: TicketWorkspace, all_tickets: list[Ticket]) -> None:
    """Groom one NEW ticket interactively. Leaves it groomed/deferred/rejected/new."""
    ui.stage(f"Groom — {ws.ticket.id}: {ws.ticket.title}")
    prompt = (
        "/backlog-groom\n\n"
        f"{ws.ticket.summary_block()}\n\n"
        f"Registered repos:\n{registry_block(ctx.repos)}\n\n"
        f"All other tickets (for duplicate detection):\n"
        f"{_backlog_digest(all_tickets, ws.ticket.id)}"
    )
    payload, _ = ctx.agent.run_json(prompt, mode="plan", workspace=ctx.settings.root)
    if not isinstance(payload, dict):
        payload = {"enrichment_summary": str(payload)}
    ws.write_artifact("grooming.json", json.dumps(payload, indent=2) + "\n")
    ui.show_markdown(_render(payload), title=f"grooming — {ws.ticket.id}")

    options = {"a": "accept", "n": "note (add your own)", "d": "defer", "s": "skip grooming"}
    if payload.get("duplicate_of"):
        options["x"] = f"drop as duplicate of {payload['duplicate_of']}"
    picked = ui.choice(options)

    if picked == "n":
        note = ui.ask_question(
            "Your note (attached to the ticket for triage/interview):",
            "goes into grooming.json as developer_note",
        )
        payload["developer_note"] = note
        ws.write_artifact("grooming.json", json.dumps(payload, indent=2) + "\n")
        picked = "a"

    if picked == "a":
        ws.transition(TicketState.GROOMED)
        ctx.store.add_comment(ws.ticket.id, f"[groomed] {payload.get('enrichment_summary', '')}")
        ui.info("groomed")
    elif picked == "d":
        ws.transition(TicketState.DEFERRED)
        ctx.store.update_status(ws.ticket.id, "deferred")
        ui.info("deferred")
    elif picked == "x":
        duplicate_of = payload.get("duplicate_of")
        ws.set_field("rejection_reason", f"duplicate of {duplicate_of}")
        ws.transition(TicketState.REJECTED)
        ctx.store.update_status(ws.ticket.id, "rejected", note=f"duplicate of {duplicate_of}")
        ui.info(f"dropped as duplicate of {duplicate_of}")
    else:
        ui.info("left ungroomed — triage will take it as-is")
