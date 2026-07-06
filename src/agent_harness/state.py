"""Per-ticket state folders: the durable, human-inspectable record of a run.

tickets/<id>/state.json is the source of truth for where a ticket is in the
pipeline; every other file in the folder is an artifact for you (and for the
retro stage) to read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import TRANSITIONS, Ticket, TicketState


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class IllegalTransition(RuntimeError):
    pass


@dataclass
class TicketWorkspace:
    ticket: Ticket
    dir: Path

    @classmethod
    def open(cls, tickets_dir: Path, ticket: Ticket) -> TicketWorkspace:
        ws = cls(ticket=ticket, dir=tickets_dir / ticket.id)
        ws.dir.mkdir(parents=True, exist_ok=True)
        if not ws.state_file.exists():
            ws._write_state(
                {
                    "ticket_id": ticket.id,
                    "title": ticket.title,
                    "status": TicketState.NEW,
                    "session_id": None,
                    "worktree": None,
                    "repo": None,
                    "history": [{"status": TicketState.NEW, "at": _now()}],
                }
            )
        return ws

    # -- state.json ---------------------------------------------------------

    @property
    def state_file(self) -> Path:
        return self.dir / "state.json"

    def _read_state(self) -> dict[str, Any]:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    @property
    def status(self) -> TicketState:
        return TicketState(self._read_state()["status"])

    def transition(self, to: TicketState) -> None:
        state = self._read_state()
        current = TicketState(state["status"])
        if to not in TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition(f"{self.ticket.id}: {current} → {to} is not a legal transition")
        state["status"] = to
        state["history"].append({"status": to, "at": _now()})
        self._write_state(state)

    def set_field(self, key: str, value: Any) -> None:
        state = self._read_state()
        state[key] = value
        self._write_state(state)

    def get_field(self, key: str) -> Any:
        return self._read_state().get(key)

    # -- artifacts -----------------------------------------------------------

    def write_artifact(self, name: str, content: str) -> Path:
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def append_artifact(self, name: str, content: str) -> Path:
        path = self.dir / name
        with path.open("a", encoding="utf-8") as f:
            f.write(content)
        return path

    def read_artifact(self, name: str) -> str | None:
        path = self.dir / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    def next_plan_version(self) -> int:
        return len(list(self.dir.glob("plan-v*.md"))) + 1

    def latest_plan(self) -> str | None:
        plans = sorted(self.dir.glob("plan-v*.md"))
        return plans[-1].read_text(encoding="utf-8") if plans else None


def append_metrics(metrics_file: Path, row: dict[str, Any]) -> None:
    row = {"at": _now(), **row}
    with metrics_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
