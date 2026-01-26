"""update_todo tool - markdown checklist for task tracking (aligned with Copilot CLI)."""
from __future__ import annotations

from pathlib import Path

from ..types import ToolResult
from .shared import ensure_inside_workspace


def plan_file() -> Path:
    return Path.cwd() / ".steward-todo.md"


def tool_update_todo(todos: str) -> ToolResult:
    """Manage tasks with a markdown checklist. Use frequently to track progress.

    Args:
        todos: A markdown checklist using '- [ ]' and '- [x]' format
    """
    plan_path = plan_file()
    ensure_inside_workspace(plan_path, must_exist=False)

    # Parse and validate markdown checklist
    lines = todos.strip().split("\n")
    validated_lines = []
    pending_count = 0
    completed_count = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            validated_lines.append("")
            continue
        # Accept markdown checkbox format
        if stripped.startswith("- [ ]"):
            pending_count += 1
            validated_lines.append(stripped)
        elif stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            completed_count += 1
            validated_lines.append(stripped.replace("- [X]", "- [x]"))
        else:
            # Allow headers and other markdown
            validated_lines.append(stripped)

    content = "\n".join(validated_lines)
    plan_path.write_text(content, encoding="utf8")

    total = pending_count + completed_count
    summary = f"TODO list updated: {completed_count}/{total} completed" if total > 0 else "TODO list updated"

    return {
        "id": "update_todo",
        "output": f"{summary}\n\n{content}",
    }
