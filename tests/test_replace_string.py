"""Tests for replace_string_in_file and multi_replace_string_in_file tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from steward.tools.multi_replace_string_in_file import tool_multi_replace_string_in_file as multi_replace_handler
from steward.tools.replace_string_in_file import tool_replace_string_in_file as replace_handler


@pytest.mark.parametrize(
    "initial,old,new,expected",
    [
        ("def foo():\n    return 42\n", "return 42", "return 100", "def foo():\n    return 100\n"),
        (
            "def foo():\n    x = 1\n    return x\n",
            "    x = 1\n    return x",
            "    y = 2\n    return y",
            "def foo():\n    y = 2\n    return y\n",
        ),
    ],
)
def test_replace_string_success(sandbox: Path, make_file, initial, old, new, expected):
    f = make_file(initial, "test.py")
    result = replace_handler(path="test.py", oldString=old, newString=new)
    assert "test.py" in result["output"]
    assert f.read_text(encoding="utf8") == expected


@pytest.mark.parametrize(
    "content,old,error_match",
    [
        ("def foo():\n    return 42\n", "return 99", "String not found"),
        ("x = 42\ny = 42\n", "42", "appears 2 times"),
    ],
)
def test_replace_string_errors(sandbox: Path, make_file, content, old, error_match):
    make_file(content, "test.py")
    with pytest.raises(ValueError, match=error_match):
        replace_handler(path="test.py", oldString=old, newString="100")


def test_replace_string_missing_file(sandbox: Path):
    with pytest.raises(ValueError, match="does not exist"):
        replace_handler(path="nonexistent.py", oldString="foo", newString="bar")


def test_replace_string_outside_workspace(sandbox: Path):
    with pytest.raises(ValueError, match="outside workspace"):
        replace_handler(path="/etc/passwd", oldString="root", newString="admin")


def test_multi_replace_basic(sandbox: Path):
    (sandbox / "file1.py").write_text("x = 1\n", encoding="utf8")
    (sandbox / "file2.py").write_text("y = 2\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "file1.py", "oldString": "x = 1", "newString": "x = 10"},
            {"path": "file2.py", "oldString": "y = 2", "newString": "y = 20"},
        ]
    )

    assert "Successfully replaced in 2 file(s)" in result["output"]
    assert (sandbox / "file1.py").read_text(encoding="utf8") == "x = 10\n"
    assert (sandbox / "file2.py").read_text(encoding="utf8") == "y = 20\n"


def test_multi_replace_same_file(sandbox: Path, make_file):
    make_file("def foo():\n    return 1\n\ndef bar():\n    return 2\n", "test.py")

    result = multi_replace_handler(
        replacements=[
            {"path": "test.py", "oldString": "return 1", "newString": "return 10"},
            {"path": "test.py", "oldString": "return 2", "newString": "return 20"},
        ]
    )

    assert "Successfully replaced in 2 file(s)" in result["output"]
    content = (sandbox / "test.py").read_text(encoding="utf8")
    assert "return 10" in content
    assert "return 20" in content


def test_multi_replace_partial_failure(sandbox: Path):
    (sandbox / "file1.py").write_text("x = 1\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "file1.py", "oldString": "x = 1", "newString": "x = 10"},
            {"path": "missing.py", "oldString": "foo", "newString": "bar"},
        ]
    )

    assert "Successfully replaced in 1 file(s)" in result["output"]
    assert "Failed 1 replacement(s)" in result["output"]
    assert result.get("error") is True


@pytest.mark.parametrize(
    "replacements,error_match",
    [
        ([], "cannot be empty"),
    ],
)
def test_multi_replace_validation(sandbox: Path, replacements, error_match):
    with pytest.raises(ValueError, match=error_match):
        multi_replace_handler(replacements=replacements)


def test_multi_replace_invalid_item(sandbox: Path):
    (sandbox / "file1.py").write_text("x = 1\n", encoding="utf8")

    result = multi_replace_handler(
        replacements=[
            {"path": "file1.py", "oldString": "x = 1", "newString": "x = 10"},
            {"path": "file1.py", "oldString": 123},  # Invalid: not a string
        ]
    )

    assert "Successfully replaced in 1 file(s)" in result["output"]
    assert "Failed 1 replacement(s)" in result["output"]
    assert "'oldString' must be a string" in result["output"]
