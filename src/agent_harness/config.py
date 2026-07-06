"""Settings from the environment and the repos.toml registry."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RepoConfig:
    """One target repo the loop is allowed to work in."""

    name: str
    path: Path
    default_branch: str = "main"
    test_command: str | None = None
    # DevOps project names and/or ticket tags that map tickets to this repo.
    projects: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Settings:
    root: Path  # orchestrator repo root
    tickets_file: Path
    model: str = "auto"
    agent_bin: str = "agent"

    @classmethod
    def from_env(cls, root: Path | None = None) -> Settings:
        root = (root or Path.cwd()).resolve()
        tickets_file = Path(os.environ.get("LOOP_TICKETS_FILE", "data/tickets.sample.json"))
        if not tickets_file.is_absolute():
            tickets_file = root / tickets_file
        return cls(
            root=root,
            tickets_file=tickets_file,
            model=os.environ.get("LOOP_MODEL", "auto"),
            agent_bin=os.environ.get("LOOP_AGENT_BIN", "agent"),
        )

    @property
    def tickets_dir(self) -> Path:
        return self.root / "tickets"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def metrics_file(self) -> Path:
        return self.root / "metrics.jsonl"


def load_repos(path: Path) -> dict[str, RepoConfig]:
    """Load repos.toml: `[repos.<name>]` tables keyed by repo name."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    repos: dict[str, RepoConfig] = {}
    for name, entry in raw.get("repos", {}).items():
        repos[name] = RepoConfig(
            name=name,
            path=Path(entry["path"]).expanduser(),
            default_branch=entry.get("default_branch", "main"),
            test_command=entry.get("test_command"),
            projects=list(entry.get("projects", [])),
            tags=list(entry.get("tags", [])),
        )
    return repos


def registry_block(repos: dict[str, RepoConfig]) -> str:
    """Registry rendered for the triage prompt, so the agent can map ticket → repo."""
    lines = []
    for r in repos.values():
        lines.append(
            f"- repo '{r.name}' at {r.path} (default branch {r.default_branch}); "
            f"DevOps projects: {r.projects or '[]'}; tags: {r.tags or '[]'}"
        )
    return "\n".join(lines) or "(no repos registered)"
