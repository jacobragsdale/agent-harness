#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Own the small, gated lifecycle for one accepted work brief."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TICKET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
STAGES = ("understand", "plan-review", "implement", "validate", "pr", "done")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def harness_root(root: str | None) -> Path:
    return Path(root).resolve() if root else Path(__file__).resolve().parents[4]


def item_dir(root: Path, ticket_id: str) -> Path:
    if not TICKET_ID.fullmatch(ticket_id):
        raise ValueError("ticket ID may contain only letters, numbers, periods, underscores, and hyphens")
    return root / ".agents" / "work-items" / ticket_id


def state_path(root: Path, ticket_id: str) -> Path:
    return item_dir(root, ticket_id) / "state.json"


def load(root: Path, ticket_id: str) -> tuple[Path, dict[str, Any]]:
    path = state_path(root, ticket_id)
    if not path.is_file():
        raise ValueError(f"no state for {ticket_id}; run init first")
    return path, json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    root = harness_root(args.root)
    item = item_dir(root, args.ticket_id)
    brief = item / "BRIEF.md"
    path = item / "state.json"
    if path.exists():
        print(f"{path} already exists — resuming at {load(root, args.ticket_id)[1]['stage']}")
        return 0
    if not brief.is_file():
        raise ValueError(f"accepted work brief does not exist: {brief}")
    state: dict[str, Any] = {
        "ticket_id": args.ticket_id,
        "stage": "understand",
        "brief_path": "BRIEF.md",
        "plan_path": "PLAN.md",
        "plan_approved": False,
        "branch": None,
        "validation": {"status": "pending", "reason": None, "at": None},
        "pr_url": None,
        "history": [{"stage": "understand", "at": now()}],
    }
    save(path, state)
    print(f"initialized {path} at understand")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    _, state = load(harness_root(args.root), args.ticket_id)
    print(json.dumps(state, indent=2))
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    _, state = load(harness_root(args.root), args.ticket_id)
    print(state["stage"])
    return 0


def cmd_approve_plan(args: argparse.Namespace) -> int:
    root = harness_root(args.root)
    path, state = load(root, args.ticket_id)
    if state["stage"] != "plan-review":
        raise ValueError("plan approval is only valid during plan-review")
    if not (path.parent / state["plan_path"]).is_file():
        raise ValueError("cannot approve a missing PLAN.md")
    state["plan_approved"] = True
    save(path, state)
    print("recorded explicit plan approval")
    return 0


def cmd_record_branch(args: argparse.Namespace) -> int:
    path, state = load(harness_root(args.root), args.ticket_id)
    if not args.branch.strip():
        raise ValueError("branch cannot be empty")
    state["branch"] = args.branch.strip()
    save(path, state)
    print(f"recorded branch {state['branch']}")
    return 0


def cmd_invalidate_validation(args: argparse.Namespace) -> int:
    path, state = load(harness_root(args.root), args.ticket_id)
    state["validation"] = {"status": "pending", "reason": None, "at": None}
    save(path, state)
    print("validation invalidated")
    return 0


def cmd_record_validation(args: argparse.Namespace) -> int:
    root = harness_root(args.root)
    path, state = load(root, args.ticket_id)
    validation = path.parent / "VALIDATION.md"
    if not validation.is_file():
        raise ValueError("VALIDATION.md does not exist; run validate.py first")
    if args.result == "overridden" and not args.reason.strip():
        raise ValueError("an overridden validation result requires the developer's exact reason")
    if args.result == "passed" and args.reason:
        raise ValueError("a passed validation result does not take an override reason")
    state["validation"] = {
        "status": args.result,
        "reason": args.reason.strip() or None,
        "at": now(),
    }
    save(path, state)
    print(f"recorded validation {args.result}")
    return 0


def cmd_record_pr(args: argparse.Namespace) -> int:
    path, state = load(harness_root(args.root), args.ticket_id)
    if not args.url.startswith(("https://", "http://")):
        raise ValueError("pull-request URL must start with http:// or https://")
    state["pr_url"] = args.url
    save(path, state)
    print(f"recorded pull request {args.url}")
    return 0


def gate_message(path: Path, state: dict[str, Any]) -> str | None:
    stage = state["stage"]
    if stage == "understand" and not (path.parent / state["plan_path"]).is_file():
        return "PLAN.md does not exist"
    if stage == "plan-review" and not state["plan_approved"]:
        return "the developer has not explicitly approved PLAN.md"
    if stage == "implement" and not state["branch"]:
        return "no implementation branch has been recorded"
    if stage == "validate" and state["validation"]["status"] not in {"passed", "overridden"}:
        return "validation is neither passed nor explicitly overridden"
    if stage == "pr" and not state["pr_url"]:
        return "no pull-request URL has been recorded"
    return None


def cmd_advance(args: argparse.Namespace) -> int:
    path, state = load(harness_root(args.root), args.ticket_id)
    current = state["stage"]
    if current == "done":
        print("already done")
        return 0
    blocked = gate_message(path, state)
    if blocked:
        print(f"BLOCKED: cannot leave {current} — {blocked}", file=sys.stderr)
        return 2
    next_stage = STAGES[STAGES.index(current) + 1]
    state["stage"] = next_stage
    state["history"].append({"stage": next_stage, "at": now()})
    save(path, state)
    print(f"advanced: {current} -> {next_stage}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="harness root (defaults to this skill's repository)")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="start a development lifecycle")
    init.add_argument("ticket_id")
    init.set_defaults(func=cmd_init)
    for name, func, help_text in (
        ("show", cmd_show, "show complete ticket state"),
        ("stage", cmd_stage, "print only the current stage"),
        ("approve-plan", cmd_approve_plan, "record explicit plan approval"),
        ("invalidate-validation", cmd_invalidate_validation, "require validation again"),
        ("advance", cmd_advance, "advance one gated stage"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("ticket_id")
        command.set_defaults(func=func)

    branch = sub.add_parser("record-branch", help="record the implementation branch")
    branch.add_argument("ticket_id")
    branch.add_argument("branch")
    branch.set_defaults(func=cmd_record_branch)

    validation = sub.add_parser("record-validation", help="record a validation outcome")
    validation.add_argument("ticket_id")
    validation.add_argument("--result", choices=("passed", "overridden"), required=True)
    validation.add_argument("--reason", default="", help="required verbatim reason for an override")
    validation.set_defaults(func=cmd_record_validation)

    pull_request = sub.add_parser("record-pr", help="record the created pull request")
    pull_request.add_argument("ticket_id")
    pull_request.add_argument("url")
    pull_request.set_defaults(func=cmd_record_pr)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
