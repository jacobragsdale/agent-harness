#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Create and inspect the Markdown work briefs shared by the two skills."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TICKET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def harness_root(root: str | None) -> Path:
    return Path(root).resolve() if root else Path(__file__).resolve().parents[4]


def brief_path(root: Path, ticket_id: str) -> Path:
    if not TICKET_ID.fullmatch(ticket_id):
        raise ValueError("ticket ID may contain only letters, numbers, periods, underscores, and hyphens")
    return root / ".agents" / "work-items" / ticket_id / "BRIEF.md"


def read_description(args: argparse.Namespace) -> str:
    if args.description_file:
        path = Path(args.description_file)
        if not path.is_file():
            raise ValueError(f"description file does not exist: {path}")
        return path.read_text(encoding="utf-8").strip()
    return args.description.strip()


def cmd_init(args: argparse.Namespace) -> int:
    root = harness_root(args.root)
    path = brief_path(root, args.ticket_id)
    if path.exists():
        raise ValueError(f"brief already exists: {path}")
    description = read_description(args) or "(Source description was not provided.)"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# Work brief: {args.ticket_id} — {args.title}

## Source

- Ticket: {args.source}

## Problem

{description}

## Triage

- Status: draft
- Target repository: {args.repo}
- Priority:
- Why now:

## Acceptance criteria

- (define during triage)

## Constraints and out of scope

- (define during triage)

## Dependencies, risks, and open questions

- (define during triage)
""",
        encoding="utf-8",
    )
    print(path)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = harness_root(args.root)
    work_items = root / ".agents" / "work-items"
    briefs = sorted(work_items.glob("*/BRIEF.md")) if work_items.exists() else []
    for path in briefs:
        status = "unknown"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- Status:"):
                status = line.partition(":")[2].strip() or "unknown"
                break
        print(f"{path.parent.name}\t{status}\t{path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    path = brief_path(harness_root(args.root), args.ticket_id)
    if not path.is_file():
        raise ValueError(f"brief does not exist: {path}")
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="harness root (defaults to this skill's repository)")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a draft work brief")
    init.add_argument("--id", dest="ticket_id", required=True, help="source ticket ID")
    init.add_argument("--title", required=True, help="source ticket title")
    init.add_argument("--source", required=True, help="ticket URL or source reference")
    init.add_argument("--repo", required=True, help="target repository name and local path")
    description = init.add_mutually_exclusive_group()
    description.add_argument("--description", default="", help="short source description")
    description.add_argument("--description-file", help="UTF-8 file containing the source description")
    init.set_defaults(func=cmd_init)

    list_parser = sub.add_parser("list", help="list current work briefs")
    list_parser.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="print one work brief")
    show.add_argument("ticket_id", help="source ticket ID")
    show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
