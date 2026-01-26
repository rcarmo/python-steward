"""Tests for grep tool."""
from __future__ import annotations

from pathlib import Path


def test_grep_finds_matches(tool_handlers, sandbox: Path):
    (sandbox / "a.txt").write_text("hello world\nfoo bar\n", encoding="utf8")
    (sandbox / "b.txt").write_text("another hello\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "hello"})
    assert "a.txt" in result["output"]
    assert "b.txt" in result["output"]


def test_grep_output_mode_content(tool_handlers, sandbox: Path):
    (sandbox / "test.py").write_text("def foo():\n    return 42\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "foo", "output_mode": "content", "-n": True})
    assert "test.py:1:" in result["output"]
    assert "def foo" in result["output"]


def test_grep_output_mode_count(tool_handlers, sandbox: Path):
    (sandbox / "test.txt").write_text("foo\nfoo\nbar\nfoo\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "foo", "output_mode": "count"})
    assert "test.txt:3" in result["output"]


def test_grep_glob_filter(tool_handlers, sandbox: Path):
    (sandbox / "code.py").write_text("hello python\n", encoding="utf8")
    (sandbox / "code.js").write_text("hello javascript\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "hello", "glob": "*.py"})
    assert "code.py" in result["output"]
    assert "code.js" not in result["output"]


def test_grep_case_insensitive(tool_handlers, sandbox: Path):
    (sandbox / "test.txt").write_text("Hello World\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "hello", "-i": True})
    assert "test.txt" in result["output"]


def test_grep_context(tool_handlers, sandbox: Path):
    (sandbox / "test.txt").write_text("line1\nline2\nmatch\nline4\nline5\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "match", "output_mode": "content", "-C": 1})
    assert "line2" in result["output"]
    assert "line4" in result["output"]


def test_grep_no_matches(tool_handlers, sandbox: Path):
    (sandbox / "test.txt").write_text("nothing here\n", encoding="utf8")
    result = tool_handlers["grep"]({"pattern": "xyz123"})
    assert "No matches" in result["output"]
