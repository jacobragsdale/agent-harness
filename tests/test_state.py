import pytest

from agent_harness.models import Ticket, TicketState
from agent_harness.state import IllegalTransition, TicketWorkspace


@pytest.fixture
def ticket():
    return Ticket(id="42", title="t", description="d", project="P")


def test_new_workspace_starts_new(tmp_path, ticket):
    ws = TicketWorkspace.open(tmp_path, ticket)
    assert ws.status == TicketState.NEW
    assert ws.state_file.exists()


def test_legal_transition_chain(tmp_path, ticket):
    ws = TicketWorkspace.open(tmp_path, ticket)
    for state in (
        TicketState.TRIAGED,
        TicketState.INTERVIEWING,
        TicketState.AWAITING_APPROVAL,
        TicketState.APPROVED,
        TicketState.EXECUTING,
        TicketState.VALIDATING,
        TicketState.PR_OPEN,
        TicketState.DONE,
    ):
        ws.transition(state)
    assert ws.status == TicketState.DONE


def test_cannot_skip_approval_gate(tmp_path, ticket):
    ws = TicketWorkspace.open(tmp_path, ticket)
    ws.transition(TicketState.TRIAGED)
    with pytest.raises(IllegalTransition):
        ws.transition(TicketState.EXECUTING)


def test_state_survives_reopen(tmp_path, ticket):
    ws = TicketWorkspace.open(tmp_path, ticket)
    ws.transition(TicketState.TRIAGED)
    ws.set_field("repo", "billing")
    reopened = TicketWorkspace.open(tmp_path, ticket)
    assert reopened.status == TicketState.TRIAGED
    assert reopened.get_field("repo") == "billing"


def test_plan_versioning(tmp_path, ticket):
    ws = TicketWorkspace.open(tmp_path, ticket)
    assert ws.next_plan_version() == 1
    ws.write_artifact("plan-v1.md", "first")
    ws.write_artifact("plan-v2.md", "second")
    assert ws.next_plan_version() == 3
    assert ws.latest_plan() == "second"
