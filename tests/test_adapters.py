import json

from agent_harness.adapters.prs import MockPRClient
from agent_harness.adapters.tickets import MockTicketStore


def _journal_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_mock_store_reads_export_and_journals_writes(tmp_path):
    export = tmp_path / "tickets.json"
    export.write_text(
        json.dumps({"tickets": [{"id": 4211, "title": "T", "description": "D", "project": "P"}]}),
        encoding="utf-8",
    )
    journal = tmp_path / "journal.jsonl"
    store = MockTicketStore(export, journal)

    tickets = store.fetch_tickets()
    assert len(tickets) == 1
    assert tickets[0].id == "4211"  # ids normalized to str

    store.update_status("4211", "triaged", note="ok")
    store.add_comment("4211", "hello")
    ops = [entry["op"] for entry in _journal_lines(journal)]
    assert ops == ["update_status", "add_comment"]


def test_mock_pr_client_journals(tmp_path):
    journal = tmp_path / "journal.jsonl"
    client = MockPRClient(journal)
    ref = client.create_pr("billing", "ticket-1", "main", "title", "body")
    assert ref.url.startswith("mock://pr/billing/")
    entry = _journal_lines(journal)[0]
    assert entry["op"] == "create_pr"
    assert entry["source_branch"] == "ticket-1"
