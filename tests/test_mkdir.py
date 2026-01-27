"""Tests for mkdir tool."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize("path,expected_output", [
    ("newdir", "Created"),
    ("a/b/c", "Created"),
])
def test_mkdir_creates_directory(tool_handlers, sandbox: Path, path, expected_output):
    result = tool_handlers["mkdir"]({"path": path})
    assert expected_output in result["output"]
    assert (sandbox / path).is_dir()


def test_mkdir_existing_is_ok(tool_handlers, sandbox: Path):
    (sandbox / "existing").mkdir()
    result = tool_handlers["mkdir"]({"path": "existing"})
    assert "already exists" in result["output"]
