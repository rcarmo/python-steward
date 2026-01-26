"""Tests for create tool."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_create_file(tool_handlers, sandbox: Path):
    result = tool_handlers["create"]({"path": "new.txt", "file_text": "hello world"})
    assert "Created" in result["output"]
    assert (sandbox / "new.txt").read_text() == "hello world"


def test_create_with_nested_dirs(tool_handlers, sandbox: Path):
    result = tool_handlers["create"]({"path": "a/b/c/file.txt", "file_text": "nested"})
    assert "Created" in result["output"]
    assert (sandbox / "a/b/c/file.txt").read_text() == "nested"


def test_create_fails_if_exists(tool_handlers, sandbox: Path):
    (sandbox / "exists.txt").write_text("original", encoding="utf8")
    with pytest.raises(ValueError, match="already exists"):
        tool_handlers["create"]({"path": "exists.txt", "file_text": "new"})


def test_create_empty_file(tool_handlers, sandbox: Path):
    result = tool_handlers["create"]({"path": "empty.txt"})
    assert "Created" in result["output"]
    assert (sandbox / "empty.txt").read_text() == ""
