"""Pull-request adapters. Mock journals; the Azure Repos stub is for later."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PrRef:
    id: str
    url: str


class PRClient(Protocol):
    def create_pr(
        self, repo_name: str, source_branch: str, target_branch: str, title: str, body: str
    ) -> PrRef: ...


class MockPRClient:
    """Journals the PR that *would* have been opened; returns a fake ref."""

    def __init__(self, journal_file: Path) -> None:
        self.journal_file = journal_file
        self._counter = 0

    def create_pr(
        self, repo_name: str, source_branch: str, target_branch: str, title: str, body: str
    ) -> PrRef:
        self._counter += 1
        ref = PrRef(id=f"mock-{self._counter}", url=f"mock://pr/{repo_name}/{self._counter}")
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_file.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "op": "create_pr",
                        "repo": repo_name,
                        "source_branch": source_branch,
                        "target_branch": target_branch,
                        "title": title,
                        "body": body,
                        "pr": ref.url,
                    }
                )
                + "\n"
            )
        return ref


class AzReposPRClient:
    """Real PR creation — intentionally unimplemented.

    On the work machine: push the branch, then `az repos pr create` (or
    `gh pr create` for GitHub-hosted repos).
    """

    def create_pr(
        self, repo_name: str, source_branch: str, target_branch: str, title: str, body: str
    ) -> PrRef:
        raise NotImplementedError("push branch + `az repos pr create` here")
