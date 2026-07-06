import json

import pytest

from agent_harness.cursor import extract_json_payload


def test_extracts_last_fenced_block():
    text = (
        "Here is my thinking...\n"
        '```json\n{"draft": true}\n```\n'
        "Actually, final answer:\n"
        '```json\n{"status": "ready"}\n```\n'
    )
    assert extract_json_payload(text) == {"status": "ready"}


def test_accepts_bare_json():
    assert extract_json_payload('{"a": 1}') == {"a": 1}


def test_raises_on_prose():
    with pytest.raises(json.JSONDecodeError):
        extract_json_payload("no json here at all")


def test_multiline_payload_with_arrays():
    text = 'prefix\n```json\n{\n  "questions": [\n    {"id": "q1"}\n  ]\n}\n```'
    assert extract_json_payload(text) == {"questions": [{"id": "q1"}]}
