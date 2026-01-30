"""replace_string_in_file tool."""

from __future__ import annotations

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def tool_replace_string_in_file(path: str, oldString: str, newString: str) -> ToolResult:
    """Replace exact string in a file.

    Args:
        path: Path to the file to modify
        oldString: The exact string to find and replace
        newString: The replacement string
    """
    abs_path = normalize_path(path)
    ensure_inside_workspace(abs_path, must_exist=False)

    if not abs_path.exists():
        raise ValueError(f"File does not exist: {rel_path(abs_path)}")

    content = abs_path.read_text(encoding="utf8")

    if oldString not in content:
        raise ValueError(f"String not found in {rel_path(abs_path)}")

    occurrences = content.count(oldString)
    if occurrences > 1:
        raise ValueError(f"String appears {occurrences} times in {rel_path(abs_path)}; must be unique")

    new_content = content.replace(oldString, newString, 1)
    abs_path.write_text(new_content, encoding="utf8")

    return {
        "id": "replace_string_in_file",
        "output": f"Replaced 1 occurrence in {rel_path(abs_path)}",
        "next_tool": ["view", "git_diff"],
    }
