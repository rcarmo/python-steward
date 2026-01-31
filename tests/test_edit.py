"""Tests for edit tool."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "initial,old_str,new_str,expected_output,expected_content",
    [
        ("hello world\n", "world", "universe", "Replaced", "hello universe\n"),
        (
            "def foo():\n    pass\n",
            "def foo():\n    pass",
            "def foo():\n    return 42",
            "Replaced",
            "def foo():\n    return 42\n",
        ),
        ("hello world\n", " world", "", "Deleted", "hello\n"),
    ],
)
def test_edit_success(
    tool_handlers, sandbox: Path, make_file, initial, old_str, new_str, expected_output, expected_content
):
    f = make_file(initial, "test.txt")
    result = tool_handlers["edit"]({"path": "test.txt", "old_str": old_str, "new_str": new_str})
    assert expected_output in result["output"]
    assert f.read_text() == expected_content


@pytest.mark.parametrize(
    "content,old_str,error_match",
    [
        ("hello", "xyz", "not found"),
        ("foo foo foo", "foo", "appears 3 times"),
    ],
)
def test_edit_fails(tool_handlers, sandbox: Path, make_file, content, old_str, error_match):
    make_file(content, "test.txt")
    with pytest.raises(ValueError, match=error_match):
        tool_handlers["edit"]({"path": "test.txt", "old_str": old_str, "new_str": "abc"})
