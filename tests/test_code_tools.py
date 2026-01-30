"""Tests for get_changed_files and list_code_usages tools."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_get_changed_files_in_repo(tool_handlers, sandbox: Path):
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=sandbox, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=sandbox, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=sandbox, capture_output=True)

    # Create and add a file
    (sandbox / "test.txt").write_text("content", encoding="utf8")
    subprocess.run(["git", "add", "test.txt"], cwd=sandbox, capture_output=True)

    result = tool_handlers["get_changed_files"]({})
    assert "output" in result


def test_list_code_usages(tool_handlers, sandbox: Path):
    # Create some code files
    (sandbox / "code.py").write_text("def my_function():\n    pass\n\nmy_function()\n", encoding="utf8")

    result = tool_handlers["list_code_usages"]({"symbolName": "my_function"})
    assert "output" in result


def test_list_code_usages_no_matches(tool_handlers, sandbox: Path):
    (sandbox / "code.py").write_text("def foo():\n    pass\n", encoding="utf8")

    result = tool_handlers["list_code_usages"]({"symbolName": "nonexistent_symbol"})
    assert "output" in result
