"""Tests for edit tool."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def test_file(sandbox: Path):
    """Create a test file with given content."""

    def _create(content: str, name: str = "test.txt"):
        f = sandbox / name
        f.write_text(content, encoding="utf8")
        return f

    return _create


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
    tool_handlers, sandbox: Path, test_file, initial, old_str, new_str, expected_output, expected_content
):
    f = test_file(initial)
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
def test_edit_fails(tool_handlers, sandbox: Path, test_file, content, old_str, error_match):
    test_file(content)
    with pytest.raises(ValueError, match=error_match):
        tool_handlers["edit"]({"path": "test.txt", "old_str": old_str, "new_str": "abc"})
