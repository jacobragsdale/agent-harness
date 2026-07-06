"""`loop` — the single entry point.

loop run                 # babysit PRs, pick a batch, groom it, work it
loop run --batch 3       # pick 3 per batch instead of 5
loop run --ticket 1234   # one ticket, no picker
loop run --skip-groom    # no grooming pass
loop groom               # interactive grooming pass only
loop babysit             # check open PRs only
loop status              # where every ticket stands
loop sync-skills         # push skills/ to ~/.cursor/skills
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.table import Table

from . import ui
from .adapters.prs import MockPRClient
from .adapters.tickets import MockTicketStore
from .config import Settings, load_repos
from .context import LoopContext
from .cursor import CursorAgent
from .loop import babysit_open_prs, groom_backlog, run_loop
from .skills_sync import sync_skills


def _build_context(settings: Settings) -> LoopContext:
    repos_file = settings.root / "repos.toml"
    if not repos_file.exists():
        raise SystemExit("repos.toml not found — copy repos.example.toml and register your repos")
    journal = settings.tickets_dir / "journal.jsonl"
    inbox = settings.tickets_dir / "pr-inbox.json"
    return LoopContext(
        settings=settings,
        repos=load_repos(repos_file),
        agent=CursorAgent(bin_name=settings.agent_bin, model=settings.model),
        store=MockTicketStore(settings.tickets_file, journal),
        prs=MockPRClient(journal, inbox),
    )


def _require_agent(settings: Settings, ctx: LoopContext) -> None:
    if not ctx.agent.available():
        raise SystemExit(
            f"Cursor CLI binary {settings.agent_bin!r} not on PATH. Install it:\n"
            "  Windows:  irm 'https://cursor.com/install?win32=true' | iex\n"
            "  mac/linux: curl https://cursor.com/install -fsS | bash"
        )


def _cmd_run(settings: Settings, args: argparse.Namespace) -> None:
    ctx = _build_context(settings)
    _require_agent(settings, ctx)
    result = sync_skills(settings.skills_dir)
    ui.info(f"synced {len(result.synced)} skills to ~/.cursor/skills")
    if result.skipped:
        ui.info(
            f"[yellow]skipped (already exist there and are not ours): "
            f"{', '.join(result.skipped)}[/yellow]"
        )
    run_loop(
        ctx,
        only_ticket=args.ticket,
        max_tickets=args.max,
        skip_groom=args.skip_groom,
        batch_size=args.batch,
    )


def _cmd_groom(settings: Settings, _args: argparse.Namespace) -> None:
    ctx = _build_context(settings)
    _require_agent(settings, ctx)
    sync_skills(settings.skills_dir)
    tickets = ctx.store.fetch_tickets()
    groom_backlog(ctx, tickets, tickets)


def _cmd_babysit(settings: Settings, _args: argparse.Namespace) -> None:
    ctx = _build_context(settings)
    _require_agent(settings, ctx)
    sync_skills(settings.skills_dir)
    babysit_open_prs(ctx, ctx.store.fetch_tickets())


def _cmd_status(settings: Settings, _args: argparse.Namespace) -> None:
    table = Table(title="ticket loop status")
    for column in ("ticket", "title", "status", "repo", "PR"):
        table.add_column(column)
    state_files = sorted(settings.tickets_dir.glob("*/state.json"))
    for sf in state_files:
        state = json.loads(sf.read_text(encoding="utf-8"))
        table.add_row(
            state.get("ticket_id", sf.parent.name),
            (state.get("title") or "")[:50],
            state.get("status", "?"),
            state.get("repo") or "-",
            state.get("pr_url") or "-",
        )
    if not state_files:
        ui.info("no tickets processed yet")
    else:
        ui.console.print(table)


def _cmd_sync_skills(settings: Settings, _args: argparse.Namespace) -> None:
    result = sync_skills(settings.skills_dir)
    ui.info(f"synced: {', '.join(result.synced) or '(none found)'}")
    if result.skipped:
        ui.info(
            f"[yellow]skipped (already exist there and are not ours): "
            f"{', '.join(result.skipped)}[/yellow]"
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="loop", description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="orchestrator repo root")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="babysit PRs, groom backlog, then work tickets")
    run_parser.add_argument("--ticket", help="process only this ticket id")
    run_parser.add_argument("--max", type=int, default=0, help="stop after N tickets")
    run_parser.add_argument(
        "--skip-groom", action="store_true", help="skip the interactive grooming pass"
    )
    run_parser.add_argument(
        "--batch", type=int, default=5, help="tickets picked per batch (default 5)"
    )
    run_parser.set_defaults(func=_cmd_run)

    groom_parser = sub.add_parser("groom", help="interactive grooming pass over new tickets")
    groom_parser.set_defaults(func=_cmd_groom)

    babysit_parser = sub.add_parser("babysit", help="one pass over open PRs")
    babysit_parser.set_defaults(func=_cmd_babysit)

    status_parser = sub.add_parser("status", help="show every ticket's pipeline state")
    status_parser.set_defaults(func=_cmd_status)

    sync_parser = sub.add_parser("sync-skills", help="copy skills/ to ~/.cursor/skills")
    sync_parser.set_defaults(func=_cmd_sync_skills)

    args = parser.parse_args()
    settings = Settings.from_env(root=args.root)
    args.func(settings, args)


if __name__ == "__main__":
    main()
