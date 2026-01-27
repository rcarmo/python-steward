"""Tests for create tool."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize("path,content,expected_content", [
    ("new.txt", "hello world", "hello world"),
    ("a/b/c/file.txt", "nested", "nested"),
    ("empty.txt", None, ""),
])
def test_create_file(tool_handlers, sandbox: Path, path, content, expected_content):
    args = {"path": path}
    if content is not None:
        args["file_text"] = content
    result = tool_handlers["create"](args)
    assert "Created" in result["output"]
    assert (sandbox / path).read_text() == expected_content


def test_create_fails_if_exists(tool_handlers, sandbox: Path):
    (sandbox / "exists.txt").write_text("original", encoding="utf8")
    with pytest.raises(ValueError, match="already exists"):
        tool_handlers["create"]({"path": "exists.txt", "file_text": "new"})
