"""Tests for view tool."""
from __future__ import annotations

from pathlib import Path


def test_view_file(tool_handlers, sandbox: Path):
    sample = sandbox / "sample.txt"
    sample.write_text("line one\nline two\nline three\n", encoding="utf8")
    result = tool_handlers["view"]({"path": "sample.txt"})
    assert "1. line one" in result["output"]
    assert "2. line two" in result["output"]


def test_view_file_range(tool_handlers, sandbox: Path):
    sample = sandbox / "sample.txt"
    sample.write_text("one\ntwo\nthree\nfour\nfive\n", encoding="utf8")
    result = tool_handlers["view"]({"path": "sample.txt", "view_range": [2, 4]})
    assert "2. two" in result["output"]
    assert "4. four" in result["output"]
    assert "1. one" not in result["output"]


def test_view_file_range_to_end(tool_handlers, sandbox: Path):
    sample = sandbox / "sample.txt"
    sample.write_text("one\ntwo\nthree\n", encoding="utf8")
    result = tool_handlers["view"]({"path": "sample.txt", "view_range": [2, -1]})
    assert "2. two" in result["output"]
    assert "3. three" in result["output"]


def test_view_directory(tool_handlers, sandbox: Path):
    (sandbox / "subdir").mkdir()
    (sandbox / "file.txt").write_text("content", encoding="utf8")
    result = tool_handlers["view"]({"path": "."})
    assert "subdir/" in result["output"]
    assert "file.txt" in result["output"]


def test_view_truncates_large_file(tool_handlers, sandbox: Path, monkeypatch):
    monkeypatch.setenv("STEWARD_READ_MAX_BYTES", "100")
    big = sandbox / "big.txt"
    big.write_text("x" * 500, encoding="utf8")
    result = tool_handlers["view"]({"path": "big.txt"})
    assert "[truncated]" in result["output"]
