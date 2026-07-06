"""Pull-request adapters. Mock journals writes and reads a simulatable
inbox file; the Azure Repos stub is for the work machine.

Demo trick: the babysitter polls `get_pr_status()`. MockPRClient answers
from `tickets/pr-inbox.json`, which you edit by hand to simulate reviewer
comments, CI failures, or a merge — e.g.:

    {
      "ticket-4211": {
        "state": "open",
        "ci": "failing",
        "ci_log": "test_poster.py::test_dead_letter FAILED - attempt counter never increments",
        "comments": [
          {"id": "c1", "author": "alice", "path": "src/billing/poster.py",
           "line": 88, "text": "Shouldn't this cap at MAX_ATTEMPTS?"}
        ]
      }
    }

Keys are branch names. `state`: open | merged | closed. `ci`: passing |
failing | pending. Optional: `merge_conflict`: true.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PrRef:
    id: str
    url: str


@dataclass(frozen=True)
class PRStatus:
    state: str = "open"  # open | merged | closed
    ci: str = "pending"  # passing | failing | pending
    ci_log: str = ""
    merge_conflict: bool = False
    comments: list[dict] = field(default_factory=list)  # {id, author, path?, line?, text}

    def has_events(self) -> bool:
        return self.ci == "failing" or self.merge_conflict or bool(self.comments)


class PRClient(Protocol):
    def create_pr(
        self, repo_name: str, source_branch: str, target_branch: str, title: str, body: str
    ) -> PrRef: ...

    def get_pr_status(self, pr_url: str, branch: str) -> PRStatus: ...

    def post_reply(self, pr_url: str, comment_id: str, body: str) -> None: ...

    def push_branch(self, repo_name: str, branch: str) -> None: ...


class MockPRClient:
    """Journals every write; answers status reads from the pr-inbox file."""

    def __init__(self, journal_file: Path, inbox_file: Path) -> None:
        self.journal_file = journal_file
        self.inbox_file = inbox_file
        self._counter = 0

    def _journal(self, entry: dict) -> None:
        entry = {"at": datetime.now(UTC).isoformat(timespec="seconds"), **entry}
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def create_pr(
        self, repo_name: str, source_branch: str, target_branch: str, title: str, body: str
    ) -> PrRef:
        self._counter += 1
        ref = PrRef(id=f"mock-{self._counter}", url=f"mock://pr/{repo_name}/{self._counter}")
        self._journal(
            {
                "op": "create_pr",
                "repo": repo_name,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "body": body,
                "pr": ref.url,
            }
        )
        return ref

    def get_pr_status(self, pr_url: str, branch: str) -> PRStatus:
        if not self.inbox_file.exists():
            return PRStatus()
        inbox = json.loads(self.inbox_file.read_text(encoding="utf-8"))
        entry = inbox.get(branch)
        if not entry:
            return PRStatus()
        return PRStatus(
            state=entry.get("state", "open"),
            ci=entry.get("ci", "pending"),
            ci_log=entry.get("ci_log", ""),
            merge_conflict=bool(entry.get("merge_conflict", False)),
            comments=list(entry.get("comments", [])),
        )

    def post_reply(self, pr_url: str, comment_id: str, body: str) -> None:
        self._journal({"op": "post_reply", "pr": pr_url, "comment_id": comment_id, "body": body})

    def push_branch(self, repo_name: str, branch: str) -> None:
        self._journal({"op": "push_branch", "repo": repo_name, "branch": branch})


class AzReposPRClient:
    """Real PR integration — intentionally unimplemented (see TODO.md §1).

    On the work machine: `git push` from the worktree, `az repos pr create`,
    `az repos pr show` / PR threads API for status and replies.
    """

    def create_pr(
        self, repo_name: str, source_branch: str, target_branch: str, title: str, body: str
    ) -> PrRef:
        raise NotImplementedError("push branch + `az repos pr create` here")

    def get_pr_status(self, pr_url: str, branch: str) -> PRStatus:
        raise NotImplementedError("`az repos pr show` + PR threads/build status here")

    def post_reply(self, pr_url: str, comment_id: str, body: str) -> None:
        raise NotImplementedError("PR thread reply API here")

    def push_branch(self, repo_name: str, branch: str) -> None:
        raise NotImplementedError("`git -C <worktree> push -u origin <branch>` here")
