"""The bundle of collaborators every stage receives."""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.prs import PRClient
from .adapters.tickets import TicketStore
from .config import RepoConfig, Settings
from .cursor import CursorAgent


@dataclass
class LoopContext:
    settings: Settings
    repos: dict[str, RepoConfig]
    agent: CursorAgent
    store: TicketStore
    prs: PRClient

    def repo(self, name: str | None) -> RepoConfig:
        if not name or name not in self.repos:
            raise KeyError(f"unknown repo {name!r}; registered: {sorted(self.repos)}")
        return self.repos[name]
