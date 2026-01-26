"""edit tool - string replacement in files (aligned with Copilot CLI)."""
from __future__ import annotations

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def tool_edit(path: str, old_str: str, new_str: str) -> ToolResult:
    """Replace text in a file. Replaces exactly one occurrence.

    Args:
        path: Path to file to edit
        old_str: Text to find and replace - must match exactly once
        new_str: Replacement text
    """
    abs_path = normalize_path(path)
    ensure_inside_workspace(abs_path)

    if not abs_path.is_file():
        raise ValueError(f"File does not exist: {rel_path(abs_path)}")

    content = abs_path.read_text(encoding="utf8")

    # Count occurrences
    count = content.count(old_str)

    if count == 0:
        raise ValueError(f"old_str not found in {rel_path(abs_path)}")
    if count > 1:
        raise ValueError(f"old_str appears {count} times in {rel_path(abs_path)}; must be unique. Add more context to make it unique.")

    # Perform replacement
    new_content = content.replace(old_str, new_str, 1)
    abs_path.write_text(new_content, encoding="utf8")

    # Provide feedback about the change
    old_lines = len(old_str.splitlines())
    new_lines = len(new_str.splitlines())
    if old_str and not new_str:
        action = f"Deleted {old_lines} line(s)"
    elif not old_str:
        action = f"Inserted {new_lines} line(s)"
    elif old_lines == new_lines:
        action = f"Replaced {old_lines} line(s)"
    else:
        action = f"Replaced {old_lines} line(s) with {new_lines} line(s)"

    return {"id": "edit", "output": f"{action} in {rel_path(abs_path)}"}
