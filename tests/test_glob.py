"""Tests for glob tool."""
from __future__ import annotations

from pathlib import Path


def test_glob_finds_files(tool_handlers, sandbox: Path):
    (sandbox / "file1.py").write_text("", encoding="utf8")
    (sandbox / "file2.py").write_text("", encoding="utf8")
    (sandbox / "file.js").write_text("", encoding="utf8")
    result = tool_handlers["glob"]({"pattern": "*.py"})
    assert "file1.py" in result["output"]
    assert "file2.py" in result["output"]
    assert "file.js" not in result["output"]


def test_glob_recursive(tool_handlers, sandbox: Path):
    subdir = sandbox / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("", encoding="utf8")
    (sandbox / "test.py").write_text("", encoding="utf8")
    result = tool_handlers["glob"]({"pattern": "**/*.py"})
    assert "src/main.py" in result["output"]
    assert "test.py" in result["output"]


def test_glob_brace_expansion(tool_handlers, sandbox: Path):
    (sandbox / "code.ts").write_text("", encoding="utf8")
    (sandbox / "code.tsx").write_text("", encoding="utf8")
    (sandbox / "code.js").write_text("", encoding="utf8")
    result = tool_handlers["glob"]({"pattern": "*.{ts,tsx}"})
    assert "code.ts" in result["output"]
    assert "code.tsx" in result["output"]
    assert "code.js" not in result["output"]


def test_glob_no_matches(tool_handlers, sandbox: Path):
    result = tool_handlers["glob"]({"pattern": "*.xyz"})
    assert "No matching files" in result["output"]
