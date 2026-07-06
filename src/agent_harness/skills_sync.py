"""Sync canonical skills (this repo's skills/) to ~/.cursor/skills.

Cursor discovers user-global skills there, which makes our stage skills
available no matter which target repo the agent's --workspace points at.
Copy, not symlink — Windows. One direction only: this repo is canonical;
the retro stage appends learnings here and we re-sync.

Every directory we create gets a marker file; we refuse to overwrite a
directory without it, so a user's own skill that happens to share a name
(e.g. `fix-bug`) is never clobbered.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

MARKER = ".managed-by-agent-harness"


@dataclass
class SyncResult:
    synced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # existed but not ours


def sync_skills(skills_dir: Path, target_root: Path | None = None) -> SyncResult:
    target_root = target_root or Path.home() / ".cursor" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)
    result = SyncResult()
    for skill in sorted(skills_dir.iterdir()):
        if not skill.is_dir() or not (skill / "SKILL.md").exists():
            continue
        destination = target_root / skill.name
        if destination.exists():
            if not (destination / MARKER).exists():
                result.skipped.append(skill.name)
                continue
            shutil.rmtree(destination)
        shutil.copytree(skill, destination)
        (destination / MARKER).write_text(
            "Synced from the agent-harness repo; edits here are overwritten. "
            "Edit the copy in agent-harness/skills/ instead.\n",
            encoding="utf-8",
        )
        result.synced.append(skill.name)
    return result
