"""Tests for store_memory tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_store_memory_creates_file(tool_handlers, sandbox: Path):
    result = tool_handlers["store_memory"]({
        "subject": "testing",
        "fact": "Use pytest for tests.",
        "citations": "test_store_memory.py:1",
        "reason": "This helps future test tasks.",
        "category": "general",
    })
    assert "Stored memory" in result["output"]
    mem_file = sandbox / ".steward-memory.json"
    assert mem_file.exists()
    data = json.loads(mem_file.read_text())
    assert len(data["memories"]) == 1
    assert data["memories"][0]["fact"] == "Use pytest for tests."


def test_store_memory_deduplicates(tool_handlers, sandbox: Path):
    args = {
        "subject": "testing",
        "fact": "Same fact",
        "citations": "file.py:1",
        "reason": "Reason here.",
        "category": "general",
    }
    tool_handlers["store_memory"](args)
    result = tool_handlers["store_memory"](args)
    assert "already exists" in result["output"]
    data = json.loads((sandbox / ".steward-memory.json").read_text())
    assert len(data["memories"]) == 1


def test_store_memory_validates_category(tool_handlers, sandbox: Path):
    with pytest.raises(ValueError, match="category"):
        tool_handlers["store_memory"]({
            "subject": "test",
            "fact": "Test fact",
            "citations": "file:1",
            "reason": "Reason",
            "category": "invalid_category",
        })


def test_store_memory_validates_fact_length(tool_handlers, sandbox: Path):
    with pytest.raises(ValueError, match="200 characters"):
        tool_handlers["store_memory"]({
            "subject": "test",
            "fact": "x" * 250,
            "citations": "file:1",
            "reason": "Reason",
            "category": "general",
        })
