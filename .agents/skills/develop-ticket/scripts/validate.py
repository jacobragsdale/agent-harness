#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run one validation command without a shell and append its result to a work brief."""

from __future__ import annotations

import argparse
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def harness_root(root: str | None) -> Path:
    return Path(root).resolve() if root else Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="harness root (defaults to this skill's repository)")
    parser.add_argument("--ticket", required=True, help="accepted work-brief ID")
    parser.add_argument("--workdir", required=True, type=Path, help="target repository or worktree")
    parser.add_argument("--timeout", type=int, default=1200, help="timeout in seconds (default: 1200)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a validation command after --")
    if not args.workdir.is_dir():
        parser.error(f"workdir does not exist: {args.workdir}")

    root = harness_root(args.root)
    output_path = root / ".agents" / "work-items" / args.ticket / "VALIDATION.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        result = subprocess.run(
            command,
            cwd=args.workdir,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        exit_code = result.returncode
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        output = (error.stdout or "") + (error.stderr or "") + f"\nTimed out after {args.timeout}s.\n"
    except OSError as error:
        exit_code = 127
        output = f"Could not start command: {error}\n"

    verdict = "PASS" if exit_code == 0 else "FAIL"
    with output_path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"## {started} — {verdict}\n\n"
            f"- Working directory: `{args.workdir.resolve()}`\n"
            f"- Command: `{' '.join(command)}`\n"
            f"- Exit code: {exit_code}\n\n"
            f"```text\n{output.rstrip()}\n```\n\n"
        )
    print(f"{verdict}: {output_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
