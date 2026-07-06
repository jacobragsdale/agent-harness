from pathlib import Path

import pytest

from agent_harness.config import Settings
from agent_harness.context import LoopContext
from agent_harness.models import Ticket, TicketState
from agent_harness.stages.pick import _digest, workable_tickets
from agent_harness.state import TicketWorkspace


def _ticket(tid, **kw):
    return Ticket(id=tid, title=f"t{tid}", description="d", project="P", **kw)


@pytest.fixture
def ctx(tmp_path):
    settings = Settings(root=tmp_path, tickets_file=tmp_path / "tickets.json")
    return LoopContext(settings=settings, repos={}, agent=None, store=None, prs=None)  # type: ignore[arg-type]


def _advance(tickets_dir: Path, ticket: Ticket, *states: TicketState) -> None:
    ws = TicketWorkspace.open(tickets_dir, ticket)
    for s in states:
        ws.transition(s)


def test_peek_status_never_creates_folder(tmp_path):
    assert TicketWorkspace.peek_status(tmp_path, "999") is None
    assert not (tmp_path / "999").exists()


def test_workable_filters_terminal_parked_and_ignored(ctx):
    untouched = _ticket("1")
    in_flight = _ticket("2")
    parked = _ticket("3")
    done = _ticket("4")
    ignored = _ticket("5")
    tickets_dir = ctx.settings.tickets_dir
    _advance(tickets_dir, in_flight, TicketState.TRIAGED)
    _advance(
        tickets_dir,
        parked,
        TicketState.TRIAGED,
        TicketState.INTERVIEWING,
        TicketState.AWAITING_APPROVAL,
        TicketState.APPROVED,
        TicketState.EXECUTING,
        TicketState.VALIDATING,
        TicketState.PR_OPEN,
    )
    _advance(tickets_dir, done, TicketState.TRIAGED, TicketState.DEFERRED)

    result = workable_tickets(ctx, [untouched, in_flight, parked, done, ignored], {"5"})
    assert [(t.id, s) for t, s in result] == [("1", None), ("2", TicketState.TRIAGED)]
    # the untouched ticket must STAY untouched — no folder created by peeking
    assert not (tickets_dir / "1").exists()


def test_digest_includes_state_and_signal_fields():
    t = _ticket("7", tags=["bug"], extra={"iterationPath": "Sprint 42", "priority": "1"})
    line = _digest([(t, TicketState.TRIAGED)])
    assert "[triaged]" in line
    assert "Sprint 42" in line
    assert "priority=1" in line
