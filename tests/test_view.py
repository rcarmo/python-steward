"""Tests for view tool."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_file(sandbox: Path):
    """Create a sample file with numbered lines."""

    def _create(content: str, name: str = "sample.txt"):
        f = sandbox / name
        f.write_text(content, encoding="utf8")
        return f

    return _create


@pytest.mark.parametrize(
    "content,expected",
    [
        ("line one\nline two\nline three\n", ["1. line one", "2. line two"]),
    ],
)
def test_view_file(tool_handlers, sandbox: Path, sample_file, content, expected):
    sample_file(content)
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
def test_view_file_range(tool_handlers, sandbox: Path, sample_file, view_range, expected, not_expected):
    sample_file("one\ntwo\nthree\nfour\nfive\n")
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


def test_view_truncates_large_file(tool_handlers, sandbox: Path, sample_file, monkeypatch):
    monkeypatch.setenv("STEWARD_READ_MAX_BYTES", "100")
    sample_file("x" * 500, "big.txt")
    result = tool_handlers["view"]({"path": "big.txt"})
    assert "[truncated]" in result["output"]
