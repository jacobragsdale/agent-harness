"""Session picker: choose a small batch from a large backlog.

With 100+ assigned tickets, a session works ~5 at a time. One fast agent
call ranks the workable backlog (in-flight first, prod issues, stale
sprints, priority); suggestions are offered one by one and the developer
takes or ignores each. Ignored tickets are left completely untouched — no
state folder, no store writes — and aren't re-suggested this session.
"""

from __future__ import annotations

from .. import ui
from ..context import LoopContext
from ..models import TERMINAL_STATES, Ticket, TicketState
from ..state import TicketWorkspace

# extra-field keys worth surfacing to the picker when the export has them
_SIGNAL_KEYS = ("createdDate", "created", "iterationPath", "sprint", "priority", "severity")


def workable_tickets(
    ctx: LoopContext, tickets: list[Ticket], ignored: set[str]
) -> list[tuple[Ticket, TicketState | None]]:
    """Tickets this session could work: untouched, or mid-pipeline (not parked)."""
    out: list[tuple[Ticket, TicketState | None]] = []
    for t in tickets:
        if t.id in ignored:
            continue
        status = TicketWorkspace.peek_status(ctx.settings.tickets_dir, t.id)
        if status is None or (status not in TERMINAL_STATES and status != TicketState.PR_OPEN):
            out.append((t, status))
    return out


def _digest(workable: list[tuple[Ticket, TicketState | None]]) -> str:
    lines = []
    for t, status in workable:
        signals = "; ".join(f"{k}={t.extra[k]}" for k in _SIGNAL_KEYS if k in t.extra)
        tags = ",".join(t.tags) or "-"
        lines.append(
            f"- {t.id} [{status or 'new'}] ({t.project}; {tags}) {t.title}"
            + (f" | {signals}" if signals else "")
        )
    return "\n".join(lines)


def pick_batch(
    ctx: LoopContext, tickets: list[Ticket], batch_size: int, ignored: set[str]
) -> list[Ticket]:
    workable = workable_tickets(ctx, tickets, ignored)
    if not workable:
        return []
    if len(workable) <= batch_size:
        ui.info(f"only {len(workable)} workable ticket(s) — taking them all")
        return [t for t, _ in workable]

    ui.stage(f"Pick — choosing up to {batch_size} of {len(workable)} workable tickets")
    prompt = f"/ticket-pick\n\nBatch size: {batch_size}\n\nWorkable tickets:\n{_digest(workable)}"
    ranked: list[dict] = []
    try:
        payload, _ = ctx.agent.run_json(prompt, mode="plan", workspace=ctx.settings.root)
        if isinstance(payload, dict):
            ranked = [r for r in payload.get("ranked", []) if isinstance(r, dict)]
    except Exception as e:
        ui.info(f"[yellow]picker agent failed ({e}) — suggesting in file order[/yellow]")

    by_id = {t.id: t for t, _ in workable}
    suggestions: list[tuple[str, str]] = []
    seen: set[str] = set()
    for r in ranked:
        tid = str(r.get("id", ""))
        if tid in by_id and tid not in seen:
            seen.add(tid)
            suggestions.append((tid, r.get("why", "")))
    for t, _ in workable:  # fallback pool: anything the picker didn't rank
        if t.id not in seen:
            suggestions.append((t.id, "(not ranked by the picker)"))

    chosen: list[Ticket] = []
    for tid, why in suggestions:
        if len(chosen) >= batch_size:
            break
        t = by_id[tid]
        tags = ",".join(t.tags) or "-"
        ui.info(f"[bold]{t.id}[/bold] {t.title}  [dim]({t.project}; {tags})[/dim]")
        ui.info(f"  [cyan]why:[/cyan] {why}")
        picked = ui.choice(
            {"y": "yes, take it", "n": "no — skip, leave untouched", "q": "quit picking"}
        )
        if picked == "y":
            chosen.append(t)
        elif picked == "n":
            ignored.add(tid)
        else:
            break

    if chosen:
        ui.info(f"this batch: {', '.join(t.id for t in chosen)}")
    return chosen
