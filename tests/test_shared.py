"""Tests for shared utilities."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_normalize_path(sandbox: Path):
    from steward.tools.shared import normalize_path

    result = normalize_path("test.txt")
    assert result.is_absolute()


def test_rel_path(sandbox: Path):
    from steward.tools.shared import rel_path

    abs_path = sandbox / "test.txt"
    result = rel_path(abs_path)
    assert result == "test.txt"


def test_ensure_inside_workspace(sandbox: Path):
    from steward.tools.shared import ensure_inside_workspace

    # Should not raise for path inside workspace
    abs_path = sandbox / "test.txt"
    abs_path.write_text("test", encoding="utf8")
    ensure_inside_workspace(abs_path)


def test_ensure_inside_workspace_outside(sandbox: Path):
    from steward.tools.shared import ensure_inside_workspace

    # Should raise for path outside workspace
    outside = Path("/tmp/outside_workspace")
    with pytest.raises(ValueError, match="outside workspace"):
        ensure_inside_workspace(outside, must_exist=False)


def test_strip_html():
    from steward.tools.shared import strip_html

    html = "<html><body><p>Hello World</p></body></html>"
    result = strip_html(html)
    assert "Hello World" in result
    assert "<html>" not in result


def test_infer_content_type():
    from steward.tools.shared import infer_content_type

    assert infer_content_type("data:text/plain,hello") == "text/plain"
    assert infer_content_type("data:application/json;base64,e30=") == "application/json"
    assert infer_content_type("https://example.com") is None


def test_is_hidden():
    from steward.tools.shared import is_hidden

    assert is_hidden(".hidden/file.txt") is True
    assert is_hidden("normal/file.txt") is False
    assert is_hidden(".git/config") is True


def test_is_binary_buffer():
    from steward.tools.shared import is_binary_buffer

    assert is_binary_buffer(b"hello world") is False
    assert is_binary_buffer(b"binary\x00data") is True


def test_truncate_output():
    from steward.utils import truncate_output

    short = "short text"
    assert truncate_output(short, 100) == short

    long = "x" * 200
    result = truncate_output(long, 50)
    assert "[truncated]" in result
    assert len(result) < 200


def test_truncate_tool_output():
    from steward.tools.shared import truncate_tool_output

    short = "short output"
    assert truncate_tool_output(short) == short

    # Test with default limit (8000)
    long = "x" * 10000
    result = truncate_tool_output(long)
    assert "truncated" in result
    assert len(result) < 9000  # Must be truncated

    # Test with custom limit
    result2 = truncate_tool_output(long, max_chars=100)
    assert len(result2) <= 200  # includes truncation marker
    assert "truncated" in result2


def test_build_matcher_simple():
    from steward.tools.shared import build_matcher

    matcher = build_matcher(
        "hello", is_regex=False, case_sensitive=False, smart_case=False, fixed_string=False, word_match=False
    )
    assert matcher("hello world")
    assert matcher("HELLO WORLD")
    assert not matcher("goodbye")


def test_build_matcher_case_sensitive():
    from steward.tools.shared import build_matcher

    matcher = build_matcher(
        "Hello", is_regex=False, case_sensitive=True, smart_case=False, fixed_string=False, word_match=False
    )
    assert matcher("Hello world")
    assert not matcher("hello world")


def test_build_matcher_regex():
    from steward.tools.shared import build_matcher

    matcher = build_matcher(
        r"\d+", is_regex=True, case_sensitive=False, smart_case=False, fixed_string=False, word_match=False
    )
    assert matcher("test 123")
    assert not matcher("no numbers")


def test_run_captured(sandbox: Path):
    from steward.tools.shared import run_captured

    code, stdout, stderr = run_captured(["echo", "hello"], sandbox)
    assert code == 0
    assert "hello" in stdout


def test_env_cap(monkeypatch):
    from steward.tools.shared import env_cap

    monkeypatch.setenv("TEST_CAP", "500")
    assert env_cap("TEST_CAP", 100) == 500
    assert env_cap("NONEXISTENT", 100) == 100
