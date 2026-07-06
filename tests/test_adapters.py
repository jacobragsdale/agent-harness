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
    client = MockPRClient(journal, tmp_path / "pr-inbox.json")
    ref = client.create_pr("billing", "ticket-1", "main", "title", "body")
    assert ref.url.startswith("mock://pr/billing/")
    entry = _journal_lines(journal)[0]
    assert entry["op"] == "create_pr"
    assert entry["source_branch"] == "ticket-1"


def test_pr_status_defaults_when_no_inbox(tmp_path):
    client = MockPRClient(tmp_path / "j.jsonl", tmp_path / "pr-inbox.json")
    status = client.get_pr_status("mock://pr/x/1", "ticket-1")
    assert status.state == "open"
    assert not status.has_events()


def test_pr_status_reads_inbox_events(tmp_path):
    inbox = tmp_path / "pr-inbox.json"
    inbox.write_text(
        json.dumps(
            {
                "ticket-4211": {
                    "state": "open",
                    "ci": "failing",
                    "ci_log": "boom",
                    "comments": [{"id": "c1", "author": "alice", "text": "cap the retries?"}],
                }
            }
        ),
        encoding="utf-8",
    )
    client = MockPRClient(tmp_path / "j.jsonl", inbox)
    status = client.get_pr_status("mock://pr/x/1", "ticket-4211")
    assert status.has_events()
    assert status.ci == "failing"
    assert status.comments[0]["id"] == "c1"
    # unknown branch → quiet defaults
    assert not client.get_pr_status("mock://pr/x/2", "ticket-9999").has_events()


def test_pr_replies_and_push_are_journaled(tmp_path):
    journal = tmp_path / "j.jsonl"
    client = MockPRClient(journal, tmp_path / "pr-inbox.json")
    client.post_reply("mock://pr/x/1", "c1", "fixed")
    client.push_branch("billing", "ticket-1")
    ops = [entry["op"] for entry in _journal_lines(journal)]
    assert ops == ["post_reply", "push_branch"]
