"""Tests for view tool."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "content,expected",
    [
        ("line one\nline two\nline three\n", ["1. line one", "2. line two"]),
    ],
)
def test_view_file(tool_handlers, sandbox: Path, make_file, content, expected):
    make_file(content, "sample.txt")
    result = tool_handlers["view"]({"path": "sample.txt"})
    for exp in expected:
        assert exp in result["output"]


@pytest.mark.parametrize(
    "view_range,expected,not_expected",
    [
        ([2, 4], ["2. two", "4. four"], ["1. one"]),
        ([2, -1], ["2. two", "3. three"], []),
    ],
)
def test_view_file_range(tool_handlers, sandbox: Path, make_file, view_range, expected, not_expected):
    make_file("one\ntwo\nthree\nfour\nfive\n", "sample.txt")
    result = tool_handlers["view"]({"path": "sample.txt", "view_range": view_range})
    for exp in expected:
        assert exp in result["output"]
    for nexp in not_expected:
        assert nexp not in result["output"]


def test_view_directory(tool_handlers, sandbox: Path):
    (sandbox / "subdir").mkdir()
    (sandbox / "file.txt").write_text("content", encoding="utf8")
    result = tool_handlers["view"]({"path": "."})
    assert "subdir/" in result["output"]
    assert "file.txt" in result["output"]


def test_view_truncates_large_file(tool_handlers, sandbox: Path, make_file, monkeypatch):
    monkeypatch.setenv("STEWARD_READ_MAX_BYTES", "100")
    make_file("x" * 500, "big.txt")
    result = tool_handlers["view"]({"path": "big.txt"})
    assert "[truncated]" in result["output"]
