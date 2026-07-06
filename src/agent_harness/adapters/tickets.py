"""Ticket source/sink adapters.

MockTicketStore is the demo implementation: it reads the exported tickets
file and journals every write to tickets/journal.jsonl instead of touching
Azure DevOps. AzDevOpsTicketStore is the stub the work machine fills in.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..models import Ticket


class TicketStore(Protocol):
    def fetch_tickets(self) -> list[Ticket]: ...

    def update_status(self, ticket_id: str, status: str, note: str = "") -> None: ...

    def add_comment(self, ticket_id: str, comment: str) -> None: ...


class MockTicketStore:
    """Reads a local export file; journals writes instead of performing them."""

    def __init__(self, tickets_file: Path, journal_file: Path) -> None:
        self.tickets_file = tickets_file
        self.journal_file = journal_file

    def fetch_tickets(self) -> list[Ticket]:
        raw = json.loads(self.tickets_file.read_text(encoding="utf-8"))
        items = raw["tickets"] if isinstance(raw, dict) and "tickets" in raw else raw
        return [Ticket.from_dict(item) for item in items]

    def _journal(self, entry: dict) -> None:
        entry = {"at": datetime.now(UTC).isoformat(timespec="seconds"), **entry}
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def update_status(self, ticket_id: str, status: str, note: str = "") -> None:
        self._journal(
            {"op": "update_status", "ticket_id": ticket_id, "status": status, "note": note}
        )

    def add_comment(self, ticket_id: str, comment: str) -> None:
        self._journal({"op": "add_comment", "ticket_id": ticket_id, "comment": comment})


class AzDevOpsTicketStore:
    """Real Azure DevOps integration — intentionally unimplemented.

    Fill these in on the work machine (e.g. via `az boards work-item ...` or
    the REST API); the rest of the loop only talks to the TicketStore
    protocol, so nothing else changes.
    """

    def fetch_tickets(self) -> list[Ticket]:
        raise NotImplementedError("wire up Azure DevOps work-item query here")

    def update_status(self, ticket_id: str, status: str, note: str = "") -> None:
        raise NotImplementedError("wire up `az boards work-item update` here")

    def add_comment(self, ticket_id: str, comment: str) -> None:
        raise NotImplementedError("wire up work-item comment API here")
