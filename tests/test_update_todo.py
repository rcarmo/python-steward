"""Tests for update_todo tool."""

from __future__ import annotations

from pathlib import Path


def test_update_todo_creates_file(tool_handlers, sandbox: Path):
    todos = "- [ ] Task 1\n- [ ] Task 2\n- [x] Done task"
    result = tool_handlers["update_todo"]({"todos": todos})
    assert "1/3 completed" in result["output"]
    assert (sandbox / ".steward-todo.md").exists()


def test_update_todo_content(tool_handlers, sandbox: Path):
    todos = "- [ ] First\n- [x] Second"
    tool_handlers["update_todo"]({"todos": todos})
    content = (sandbox / ".steward-todo.md").read_text()
    assert "- [ ] First" in content
    assert "- [x] Second" in content


def test_update_todo_normalizes_checkbox(tool_handlers, sandbox: Path):
    todos = "- [X] Uppercase X"
    tool_handlers["update_todo"]({"todos": todos})
    content = (sandbox / ".steward-todo.md").read_text()
    assert "- [x]" in content  # Normalized to lowercase
