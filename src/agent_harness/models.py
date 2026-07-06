"""Core data types: tickets and the per-ticket state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TicketState(StrEnum):
    NEW = "new"
    GROOMED = "groomed"
    TRIAGED = "triaged"
    INTERVIEWING = "interviewing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    VALIDATING = "validating"
    PR_OPEN = "pr_open"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"
    DEFERRED = "deferred"


TERMINAL_STATES = frozenset(
    {TicketState.DONE, TicketState.FAILED, TicketState.REJECTED, TicketState.DEFERRED}
)

# Legal transitions; the orchestrator refuses anything else so a bug can't
# silently skip the approval gate. PR_OPEN is a *parked* state: run_ticket
# stops there and the babysitter drives it to done/rejected on PR events.
TRANSITIONS: dict[TicketState, frozenset[TicketState]] = {
    TicketState.NEW: frozenset(
        {
            TicketState.GROOMED,
            TicketState.TRIAGED,  # grooming skipped
            TicketState.DEFERRED,
            TicketState.REJECTED,  # e.g. confirmed duplicate at grooming
            TicketState.FAILED,
        }
    ),
    TicketState.GROOMED: frozenset(
        {TicketState.TRIAGED, TicketState.DEFERRED, TicketState.REJECTED, TicketState.FAILED}
    ),
    TicketState.TRIAGED: frozenset(
        {TicketState.INTERVIEWING, TicketState.DEFERRED, TicketState.REJECTED, TicketState.FAILED}
    ),
    TicketState.INTERVIEWING: frozenset(
        {TicketState.AWAITING_APPROVAL, TicketState.DEFERRED, TicketState.FAILED}
    ),
    TicketState.AWAITING_APPROVAL: frozenset(
        {
            TicketState.APPROVED,
            TicketState.REJECTED,
            TicketState.DEFERRED,
            TicketState.FAILED,
        }
    ),
    TicketState.APPROVED: frozenset({TicketState.EXECUTING, TicketState.FAILED}),
    TicketState.EXECUTING: frozenset({TicketState.VALIDATING, TicketState.FAILED}),
    TicketState.VALIDATING: frozenset(
        {TicketState.PR_OPEN, TicketState.REJECTED, TicketState.FAILED}
    ),
    TicketState.PR_OPEN: frozenset({TicketState.DONE, TicketState.REJECTED, TicketState.FAILED}),
}


@dataclass
class Ticket:
    """A work item as exported from Azure DevOps."""

    id: str
    title: str
    description: str
    project: str
    tags: list[str] = field(default_factory=list)
    link: str = ""
    status: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Ticket:
        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        kwargs = {k: raw[k] for k in known if k in raw}
        kwargs["id"] = str(raw.get("id", ""))
        kwargs["extra"] = {k: v for k, v in raw.items() if k not in known}
        return cls(**kwargs)

    def summary_block(self) -> str:
        """Ticket rendered for inclusion in an agent prompt."""
        tags = ", ".join(self.tags) or "(none)"
        return (
            f"Ticket {self.id}: {self.title}\n"
            f"Project: {self.project}\n"
            f"Tags: {tags}\n"
            f"Link: {self.link or '(none)'}\n"
            f"Description:\n{self.description}"
        )
