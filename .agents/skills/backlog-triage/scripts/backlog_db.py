#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Maintain the local SQLite read model used by backlog triage."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = ("System.Title", "System.WorkItemType", "System.State")
FIELD_MAP = {
    "title": "System.Title",
    "description": "System.Description",
    "acceptance_criteria": "Microsoft.VSTS.Common.AcceptanceCriteria",
    "repro_steps": "Microsoft.VSTS.TCM.ReproSteps",
    "work_item_type": "System.WorkItemType",
    "state": "System.State",
    "reason": "System.Reason",
    "team_project": "System.TeamProject",
    "area_path": "System.AreaPath",
    "iteration_path": "System.IterationPath",
    "tags": "System.Tags",
    "priority": "Microsoft.VSTS.Common.Priority",
    "backlog_rank": "Microsoft.VSTS.Common.BacklogPriority",
    "stack_rank": "Microsoft.VSTS.Common.StackRank",
    "severity": "Microsoft.VSTS.Common.Severity",
    "assigned_to": "System.AssignedTo",
    "created_at": "System.CreatedDate",
    "changed_at": "System.ChangedDate",
}
BRIEF_ID = re.compile(r"^# Work brief: ([A-Za-z0-9][A-Za-z0-9._-]*) —", re.MULTILINE)
BRIEF_STATUS = re.compile(r"^- Status:\s*(.+)$", re.MULTILINE)
BRIEF_REPOSITORY = re.compile(r"^- Target repository:\s*(.+)$", re.MULTILINE)


class TextExtractor(HTMLParser):
    block_tags = frozenset({"br", "div", "li", "p", "tr", "td", "th", "h1", "h2", "h3"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def harness_root(root: str | None) -> Path:
    return Path(root).resolve() if root else Path(__file__).resolve().parents[4]


def resource_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / name


def database_path(args: argparse.Namespace) -> Path:
    if args.database:
        return Path(args.database).expanduser().resolve()
    return harness_root(args.root) / ".agents" / "work-items" / "backlog.sqlite3"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(connection: sqlite3.Connection, rebuild_search: bool = False) -> None:
    try:
        connection.executescript(resource_path("backlog-schema.sql").read_text(encoding="utf-8"))
        if rebuild_search:
            connection.execute("INSERT INTO ticket_fts(ticket_fts) VALUES ('rebuild')")
    except sqlite3.OperationalError as error:
        if "fts5" in str(error).casefold():
            raise ValueError("SQLite must include FTS5 support for duplicate detection") from error
        raise
    connection.commit()


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        parser = TextExtractor()
        parser.feed(value)
        return parser.text()
    if isinstance(value, dict):
        for key in ("displayName", "uniqueName", "name"):
            candidate = value.get(key)
            if candidate:
                return str(candidate)
        return json.dumps(value, sort_keys=True)
    return str(value)


def optional_number(value: Any, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if integer else number


def items_from_export(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON export: {path}") from error
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("value") or payload.get("workItems") or payload.get("tickets")
    else:
        items = None
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ValueError("expected an Azure DevOps batch response with a value array of work items")
    return items


def fields_for(item: dict[str, Any]) -> dict[str, Any]:
    fields = item.get("fields", item)
    if not isinstance(fields, dict):
        raise ValueError("work item fields must be an object")
    return fields


def validate_export(items: list[dict[str, Any]]) -> None:
    problems: list[str] = []
    for item in items:
        fields = fields_for(item)
        missing = [field for field in REQUIRED_FIELDS if field not in fields]
        ticket_id = item.get("id") or fields.get("System.Id") or "?"
        if not (item.get("id") or fields.get("System.Id")):
            missing.insert(0, "System.Id")
        if missing:
            problems.append(f"{ticket_id}: {', '.join(missing)}")
    if problems:
        detail = "; ".join(problems[:5])
        raise ValueError(
            "export is missing required Azure DevOps reference fields. "
            f"Fetch the documented field list, then retry. Examples: {detail}"
        )


def import_export(args: argparse.Namespace) -> int:
    export_path = Path(args.file).expanduser().resolve()
    if not export_path.is_file():
        raise ValueError(f"export file does not exist: {export_path}")
    items = items_from_export(export_path)
    validate_export(items)
    connection = connect(database_path(args))
    try:
        initialize(connection)
        imported_at = now()
        for item in items:
            fields = fields_for(item)
            values = {name: text_value(fields.get(reference)) for name, reference in FIELD_MAP.items()}
            ticket_id = str(item.get("id") or fields["System.Id"])
            connection.execute(
                """
                INSERT INTO tickets (
                    azure_id, title, description, acceptance_criteria, repro_steps,
                    work_item_type, state, reason, team_project, area_path, iteration_path,
                    tags, priority, backlog_rank, stack_rank, severity, assigned_to,
                    created_at, changed_at, source_url, raw_json, imported_at
                ) VALUES (
                    :azure_id, :title, :description, :acceptance_criteria, :repro_steps,
                    :work_item_type, :state, :reason, :team_project, :area_path, :iteration_path,
                    :tags, :priority, :backlog_rank, :stack_rank, :severity, :assigned_to,
                    :created_at, :changed_at, :source_url, :raw_json, :imported_at
                )
                ON CONFLICT(azure_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    acceptance_criteria = excluded.acceptance_criteria,
                    repro_steps = excluded.repro_steps,
                    work_item_type = excluded.work_item_type,
                    state = excluded.state,
                    reason = excluded.reason,
                    team_project = excluded.team_project,
                    area_path = excluded.area_path,
                    iteration_path = excluded.iteration_path,
                    tags = excluded.tags,
                    priority = excluded.priority,
                    backlog_rank = excluded.backlog_rank,
                    stack_rank = excluded.stack_rank,
                    severity = excluded.severity,
                    assigned_to = excluded.assigned_to,
                    created_at = excluded.created_at,
                    changed_at = excluded.changed_at,
                    source_url = excluded.source_url,
                    raw_json = excluded.raw_json,
                    imported_at = excluded.imported_at
                """,
                {
                    "azure_id": ticket_id,
                    **values,
                    "priority": optional_number(fields.get(FIELD_MAP["priority"]), integer=True),
                    "backlog_rank": optional_number(fields.get(FIELD_MAP["backlog_rank"])),
                    "stack_rank": optional_number(fields.get(FIELD_MAP["stack_rank"])),
                    "source_url": text_value(item.get("url")),
                    "raw_json": json.dumps(item, sort_keys=True),
                    "imported_at": imported_at,
                },
            )
        connection.commit()
    finally:
        connection.close()
    print(f"imported {len(items)} work item(s) from {export_path}")
    return 0


def brief_metadata(path: Path) -> tuple[str, str, str | None]:
    if not path.is_file():
        raise ValueError(f"brief does not exist: {path}")
    content = path.read_text(encoding="utf-8")
    ticket = BRIEF_ID.search(content)
    status = BRIEF_STATUS.search(content)
    if not ticket or not status:
        raise ValueError("brief must contain its standard heading and a Status field")
    repository = BRIEF_REPOSITORY.search(content)
    return ticket.group(1), status.group(1).strip().casefold(), repository.group(1).strip() if repository else None


def record_brief(args: argparse.Namespace) -> int:
    brief = Path(args.brief).expanduser().resolve()
    ticket_id, status, repository = brief_metadata(brief)
    connection = connect(database_path(args))
    try:
        initialize(connection)
        exists = connection.execute("SELECT 1 FROM tickets WHERE azure_id = ?", (ticket_id,)).fetchone()
        if not exists:
            raise ValueError(f"ticket {ticket_id} is not in the local cache; import it before recording a brief")
        connection.execute(
            """
            INSERT INTO work_items(ticket_id, brief_path, brief_status, target_repository, synced_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                brief_path = excluded.brief_path,
                brief_status = excluded.brief_status,
                target_repository = excluded.target_repository,
                synced_at = excluded.synced_at
            """,
            (ticket_id, str(brief), status, repository, now()),
        )
        connection.commit()
    finally:
        connection.close()
    print(f"recorded work brief {ticket_id} ({status})")
    return 0


def record_decision(args: argparse.Namespace) -> int:
    if not args.rationale.strip():
        raise ValueError("a triage decision requires a nonempty rationale")
    if args.disposition == "duplicate" and not args.duplicate_of:
        raise ValueError("a duplicate decision requires --duplicate-of")
    if args.disposition != "duplicate" and args.duplicate_of:
        raise ValueError("--duplicate-of is valid only for a duplicate decision")
    connection = connect(database_path(args))
    try:
        initialize(connection)
        exists = connection.execute("SELECT 1 FROM tickets WHERE azure_id = ?", (args.ticket_id,)).fetchone()
        if not exists:
            raise ValueError(f"ticket {args.ticket_id} is not in the local cache")
        connection.execute(
            """
            INSERT INTO triage_decisions(ticket_id, disposition, rationale, duplicate_of, decided_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (args.ticket_id, args.disposition, args.rationale.strip(), args.duplicate_of, now()),
        )
        connection.commit()
    finally:
        connection.close()
    print(f"recorded {args.disposition} decision for {args.ticket_id}")
    return 0


def terminal_states(args: argparse.Namespace) -> int:
    connection = connect(database_path(args))
    try:
        initialize(connection)
        if args.action == "set":
            if not args.states:
                raise ValueError("provide at least one terminal state")
            connection.execute("DELETE FROM terminal_states")
            connection.executemany(
                "INSERT INTO terminal_states(state) VALUES (?)",
                [(state,) for state in args.states],
            )
            connection.commit()
        rows = connection.execute("SELECT state FROM terminal_states ORDER BY state COLLATE NOCASE").fetchall()
    finally:
        connection.close()
    for row in rows:
        print(row["state"])
    return 0


def named_queries() -> dict[str, str]:
    queries: dict[str, list[str]] = {}
    current: str | None = None
    for line in resource_path("triage-queries.sql").read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith("-- name: "):
            current = line.removeprefix("-- name: ").strip()
            queries[current] = []
        elif current:
            queries[current].append(line)
    return {name: "".join(sql).strip() for name, sql in queries.items()}


def fts_terms(title: str) -> str:
    terms = list(dict.fromkeys(re.findall(r"[A-Za-z0-9]{3,}", title.casefold())))[:3]
    if not terms:
        raise ValueError("ticket title has no searchable terms for duplicate detection")
    return " AND ".join(f'"{term}"' for term in terms)


def cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def show_rows(rows: list[sqlite3.Row], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps([dict(row) for row in rows], indent=2))
        return
    if not rows:
        print("(no rows)")
        return
    headers = list(rows[0].keys())
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        print("| " + " | ".join(cell(row[header]) for header in headers) + " |")


def run_query(args: argparse.Namespace) -> int:
    queries = named_queries()
    sql = queries[args.name]
    connection = connect(database_path(args))
    try:
        initialize(connection)
        params: dict[str, Any] = {"limit": args.limit, "days": args.days}
        if args.name == "duplicates":
            ticket = connection.execute("SELECT title FROM tickets WHERE azure_id = ?", (args.ticket_id,)).fetchone()
            if not ticket:
                raise ValueError(f"ticket {args.ticket_id} is not in the local cache")
            params["ticket_id"] = args.ticket_id
            params["match"] = fts_terms(ticket["title"])
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    show_rows(rows, args.output_format)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="harness root (defaults to this skill's repository)")
    parser.add_argument("--database", help="SQLite file (defaults to .agents/work-items/backlog.sqlite3)")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create or migrate the local SQLite cache")
    init.set_defaults(func=lambda args: initialize_only(args))

    importer = sub.add_parser("import-azure-export", help="upsert an Azure DevOps batch-response export")
    importer.add_argument("--file", required=True, help="JSON file with a value array of work items")
    importer.set_defaults(func=import_export)

    brief = sub.add_parser("record-brief", help="sync one BRIEF.md into the local cache")
    brief.add_argument("--brief", required=True, help="path to the standard work brief")
    brief.set_defaults(func=record_brief)

    decision = sub.add_parser("record-decision", help="record a non-selected triage decision")
    decision.add_argument("ticket_id")
    decision.add_argument("--disposition", choices=("deferred", "rejected", "duplicate"), required=True)
    decision.add_argument("--rationale", required=True)
    decision.add_argument("--duplicate-of")
    decision.set_defaults(func=record_decision)

    states = sub.add_parser("terminal-states", help="list or replace source-process terminal state names")
    states.add_argument("action", choices=("list", "set"))
    states.add_argument("states", nargs="*")
    states.set_defaults(func=terminal_states)

    query = sub.add_parser("query", help="run a named triage query")
    query.add_argument("name", choices=tuple(named_queries()))
    query.add_argument("--limit", type=int, default=20)
    query.add_argument("--days", type=int, default=30)
    query.add_argument("--ticket-id", help="required for the duplicates query")
    query.add_argument("--format", dest="output_format", choices=("markdown", "json"), default="markdown")
    query.set_defaults(func=run_query)

    args = parser.parse_args()
    if args.command == "query" and args.name == "duplicates" and not args.ticket_id:
        parser.error("query duplicates requires --ticket-id")
    try:
        return args.func(args)
    except (ValueError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def initialize_only(args: argparse.Namespace) -> int:
    path = database_path(args)
    connection = connect(path)
    try:
        initialize(connection, rebuild_search=True)
    finally:
        connection.close()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
