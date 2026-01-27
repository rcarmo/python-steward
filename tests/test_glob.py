"""Tests for glob tool."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def glob_files(sandbox: Path):
    """Create test files for glob tests."""
    def _create(files: list[str], subdirs: list[str] | None = None):
        for subdir in (subdirs or []):
            (sandbox / subdir).mkdir(parents=True, exist_ok=True)
        for name in files:
            (sandbox / name).write_text("", encoding="utf8")
    return _create


@pytest.mark.parametrize("files,subdirs,pattern,expected,not_expected", [
    # Basic pattern
    (["file1.py", "file2.py", "file.js"], None, "*.py",
     ["file1.py", "file2.py"], ["file.js"]),
    # Recursive pattern
    (["test.py", "src/main.py"], ["src"], "**/*.py",
     ["src/main.py", "test.py"], []),
    # Brace expansion
    (["code.ts", "code.tsx", "code.js"], None, "*.{ts,tsx}",
     ["code.ts", "code.tsx"], ["code.js"]),
    # No matches
    ([], None, "*.xyz",
     ["No matching files"], []),
])
def test_glob(tool_handlers, sandbox: Path, glob_files, files, subdirs, pattern, expected, not_expected):
    glob_files(files, subdirs)
    result = tool_handlers["glob"]({"pattern": pattern})
    for exp in expected:
        assert exp in result["output"]
    for nexp in not_expected:
        assert nexp not in result["output"]
