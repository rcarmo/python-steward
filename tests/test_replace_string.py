"""Tests for replace_string_in_file and multi_replace_string_in_file tools."""
from __future__ import annotations

from pathlib import Path

import pytest

from steward.tools.multi_replace_string_in_file import tool_handler as multi_replace_handler
from steward.tools.replace_string_in_file import tool_handler as replace_handler


def test_replace_string_basic(sandbox: Path) -> None:
    """Test basic string replacement."""
    test_file = sandbox / "test.py"
    test_file.write_text("def foo():\n    return 42\n", encoding="utf8")

    result = replace_handler(
        path="test.py",
        oldString="return 42",
        newString="return 100"
    )

    assert "test.py" in result["output"]
    assert test_file.read_text(encoding="utf8") == "def foo():\n    return 100\n"


def test_replace_string_multiline(sandbox: Path) -> None:
    """Test replacing multiline strings."""
    test_file = sandbox / "test.py"
    original = "def foo():\n    x = 1\n    return x\n"
    test_file.write_text(original, encoding="utf8")

    result = replace_handler(
        path="test.py",
        oldString="    x = 1\n    return x",
        newString="    y = 2\n    return y"
    )

    assert "test.py" in result["output"]
    assert test_file.read_text(encoding="utf8") == "def foo():\n    y = 2\n    return y\n"


def test_replace_string_not_found(sandbox: Path) -> None:
    """Test error when string not found."""
    test_file = sandbox / "test.py"
    test_file.write_text("def foo():\n    return 42\n", encoding="utf8")

    with pytest.raises(ValueError, match="String not found"):
        replace_handler(
            path="test.py",
            oldString="return 99",
            newString="return 100"
        )


def test_replace_string_multiple_occurrences(sandbox: Path) -> None:
    """Test error when string appears multiple times."""
    test_file = sandbox / "test.py"
    test_file.write_text("x = 42\ny = 42\n", encoding="utf8")

    with pytest.raises(ValueError, match="appears 2 times"):
        replace_handler(
            path="test.py",
            oldString="42",
            newString="100"
        )


def test_replace_string_missing_file(sandbox: Path) -> None:
    """Test error when file doesn't exist."""
    with pytest.raises(ValueError, match="does not exist"):
        replace_handler(
            path="nonexistent.py",
            oldString="foo",
            newString="bar"
        )


def test_replace_string_outside_workspace(sandbox: Path) -> None:
    """Test error when path is outside workspace."""
    with pytest.raises(ValueError, match="outside workspace"):
        replace_handler(
            path="/etc/passwd",
            oldString="root",
            newString="admin"
        )


def test_multi_replace_basic(sandbox: Path) -> None:
    """Test multiple replacements in different files."""
    file1 = sandbox / "file1.py"
    file2 = sandbox / "file2.py"
    file1.write_text("x = 1\n", encoding="utf8")
    file2.write_text("y = 2\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "file1.py", "oldString": "x = 1", "newString": "x = 10"},
            {"path": "file2.py", "oldString": "y = 2", "newString": "y = 20"},
        ]
    )

    assert "Successfully replaced in 2 file(s)" in result["output"]
    assert file1.read_text(encoding="utf8") == "x = 10\n"
    assert file2.read_text(encoding="utf8") == "y = 20\n"


def test_multi_replace_same_file(sandbox: Path) -> None:
    """Test multiple replacements in the same file."""
    test_file = sandbox / "test.py"
    test_file.write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "test.py", "oldString": "return 1", "newString": "return 10"},
            {"path": "test.py", "oldString": "return 2", "newString": "return 20"},
        ]
    )

    assert "Successfully replaced in 2 file(s)" in result["output"]
    content = test_file.read_text(encoding="utf8")
    assert "return 10" in content
    assert "return 20" in content


def test_multi_replace_partial_failure(sandbox: Path) -> None:
    """Test multi-replace with some failures."""
    file1 = sandbox / "file1.py"
    file1.write_text("x = 1\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "file1.py", "oldString": "x = 1", "newString": "x = 10"},
            {"path": "missing.py", "oldString": "foo", "newString": "bar"},
        ]
    )

    assert "Successfully replaced in 1 file(s)" in result["output"]
    assert "Failed 1 replacement(s)" in result["output"]
    assert result.get("error") is True
    assert file1.read_text(encoding="utf8") == "x = 10\n"


def test_multi_replace_empty_list(sandbox: Path) -> None:
    """Test error with empty replacements list."""
    with pytest.raises(ValueError, match="cannot be empty"):
        multi_replace_handler(replacements=[])


def test_multi_replace_invalid_item(sandbox: Path) -> None:
    """Test error with invalid replacement items."""
    file1 = sandbox / "file1.py"
    file1.write_text("x = 1\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "file1.py", "oldString": "x = 1", "newString": "x = 10"},
            {"path": "file1.py", "oldString": 123},  # Invalid: not a string
        ]
    )

    assert "Successfully replaced in 1 file(s)" in result["output"]
    assert "Failed 1 replacement(s)" in result["output"]
    assert "'oldString' must be a string" in result["output"]
