"""Tests for edit tool."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_edit_replaces_string(tool_handlers, sandbox: Path):
    f = sandbox / "test.txt"
    f.write_text("hello world\n", encoding="utf8")
    result = tool_handlers["edit"]({"path": "test.txt", "old_str": "world", "new_str": "universe"})
    assert "Replaced" in result["output"]
    assert f.read_text() == "hello universe\n"


def test_edit_multiline(tool_handlers, sandbox: Path):
    f = sandbox / "test.py"
    f.write_text("def foo():\n    pass\n", encoding="utf8")
    result = tool_handlers["edit"]({
        "path": "test.py",
        "old_str": "def foo():\n    pass",
        "new_str": "def foo():\n    return 42"
    })
    assert "Replaced" in result["output"]
    assert "return 42" in f.read_text()


def test_edit_fails_if_not_found(tool_handlers, sandbox: Path):
    f = sandbox / "test.txt"
    f.write_text("hello", encoding="utf8")
    with pytest.raises(ValueError, match="not found"):
        tool_handlers["edit"]({"path": "test.txt", "old_str": "xyz", "new_str": "abc"})


def test_edit_fails_if_not_unique(tool_handlers, sandbox: Path):
    f = sandbox / "test.txt"
    f.write_text("foo foo foo", encoding="utf8")
    with pytest.raises(ValueError, match="appears 3 times"):
        tool_handlers["edit"]({"path": "test.txt", "old_str": "foo", "new_str": "bar"})


def test_edit_delete(tool_handlers, sandbox: Path):
    f = sandbox / "test.txt"
    f.write_text("hello world\n", encoding="utf8")
    result = tool_handlers["edit"]({"path": "test.txt", "old_str": " world", "new_str": ""})
    assert "Deleted" in result["output"]
    assert f.read_text() == "hello\n"
