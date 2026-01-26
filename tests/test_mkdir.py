"""Tests for mkdir tool."""
from __future__ import annotations

from pathlib import Path


def test_mkdir_creates_directory(tool_handlers, sandbox: Path):
    result = tool_handlers["mkdir"]({"path": "newdir"})
    assert "Created" in result["output"]
    assert (sandbox / "newdir").is_dir()


def test_mkdir_creates_parents(tool_handlers, sandbox: Path):
    result = tool_handlers["mkdir"]({"path": "a/b/c"})
    assert "Created" in result["output"]
    assert (sandbox / "a/b/c").is_dir()


def test_mkdir_existing_is_ok(tool_handlers, sandbox: Path):
    (sandbox / "existing").mkdir()
    result = tool_handlers["mkdir"]({"path": "existing"})
    assert "already exists" in result["output"]
