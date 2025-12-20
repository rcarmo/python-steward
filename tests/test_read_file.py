from __future__ import annotations

from pathlib import Path


def test_reads_file(tool_handlers, sandbox: Path):
    sample = sandbox / "sample.txt"
    sample.write_text("one\ntwo\nthree\n", encoding="utf8")
    result = tool_handlers["read_file"]({"path": "sample.txt", "startLine": 1, "endLine": 2})
    assert "Lines 1-2:" in result["output"]
    assert "one\ntwo" in result["output"]


def test_truncates(tool_handlers, sandbox: Path):
    big = sandbox / "big.txt"
    big.write_text("x" * 20000, encoding="utf8")
    result = tool_handlers["read_file"]({"path": "big.txt", "maxBytes": 100, "maxLines": 1})
    assert "Lines 1-1:" in result["output"]
    assert "[truncated]" in result["output"]


def test_env_caps(tool_handlers, sandbox: Path, monkeypatch):
    monkeypatch.setenv("STEWARD_READ_MAX_BYTES", "50")
    env_file = sandbox / "env.txt"
    env_file.write_text("x" * 500, encoding="utf8")
    result = tool_handlers["read_file"]({"path": "env.txt"})
    assert "[truncated]" in result["output"]
