"""Tests for grep tool."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def grep_files(sandbox: Path):
    """Create test files for grep tests."""

    def _create(files: dict[str, str]):
        for name, content in files.items():
            (sandbox / name).write_text(content, encoding="utf8")

    return _create


@pytest.mark.parametrize(
    "files,pattern,args,expected,not_expected",
    [
        # Basic match
        ({"a.txt": "hello world\nfoo bar\n", "b.txt": "another hello\n"}, "hello", {}, ["a.txt", "b.txt"], []),
        # Output mode content with line numbers
        (
            {"test.py": "def foo():\n    return 42\n"},
            "foo",
            {"output_mode": "content", "show_line_numbers": True},
            ["test.py:1:", "def foo"],
            [],
        ),
        # Output mode count
        ({"test.txt": "foo\nfoo\nbar\nfoo\n"}, "foo", {"output_mode": "count"}, ["test.txt:3"], []),
        # Glob filter
        (
            {"code.py": "hello python\n", "code.js": "hello javascript\n"},
            "hello",
            {"glob": "*.py"},
            ["code.py"],
            ["code.js"],
        ),
        # Case insensitive
        ({"test.txt": "Hello World\n"}, "hello", {"case_insensitive": True}, ["test.txt"], []),
        # Context
        (
            {"test.txt": "line1\nline2\nmatch\nline4\nline5\n"},
            "match",
            {"output_mode": "content", "context_both": 1},
            ["line2", "line4"],
            [],
        ),
        # No matches
        ({"test.txt": "nothing here\n"}, "xyz123", {}, ["No matches"], []),
    ],
)
def test_grep(tool_handlers, sandbox: Path, grep_files, files, pattern, args, expected, not_expected):
    grep_files(files)
    result = tool_handlers["grep"]({"pattern": pattern, **args})
    for exp in expected:
        assert exp in result["output"]
    for nexp in not_expected:
        assert nexp not in result["output"]
