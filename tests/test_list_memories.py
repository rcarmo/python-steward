"""Tests for list_memories tool."""
from __future__ import annotations

import json
from pathlib import Path


def test_list_memories_empty(tool_handlers, sandbox: Path):
    result = tool_handlers["list_memories"]({})
    assert "No memories stored" in result["output"]


def test_list_memories_filters(tool_handlers, sandbox: Path):
    mem_file = sandbox / ".steward-memory.json"
    data = {
        "memories": [
            {
                "subject": "testing",
                "fact": "Use pytest.",
                "citations": "file.py:1",
                "reason": "It is the test runner. It is consistent.",
                "category": "general",
                "timestamp": "2024-01-01T00:00:00+00:00",
            },
            {
                "subject": "build",
                "fact": "Use make lint.",
                "citations": "Makefile:1",
                "reason": "It runs linting. It is consistent.",
                "category": "bootstrap_and_build",
                "timestamp": "2024-01-01T00:00:00+00:00",
            },
        ]
    }
    mem_file.write_text(json.dumps(data), encoding="utf8")

    result = tool_handlers["list_memories"]({"category": "general"})
    output = result["output"]
    assert "Use pytest." in output
    assert "Use make lint." not in output

    result = tool_handlers["list_memories"]({"subject": "build"})
    output = result["output"]
    assert "Use make lint." in output
    assert "Use pytest." not in output
