"""edit tool - string replacement in files (aligned with Copilot CLI)."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "edit",
    "description": "Make string replacements in files. Replaces exactly one occurrence of old_str with new_str. If old_str is not unique, replacement will not be performed.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Full path to file to edit. File must exist.",
            },
            "old_str": {
                "type": "string",
                "description": "The string in the file to replace. Must match exactly one occurrence.",
            },
            "new_str": {
                "type": "string",
                "description": "The new string to replace old_str with.",
            },
        },
        "required": ["path"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")

    old_str = args.get("old_str")
    new_str = args.get("new_str", "")

    if not isinstance(old_str, str):
        raise ValueError("'old_str' must be a string")
    if not isinstance(new_str, str):
        raise ValueError("'new_str' must be a string")

    abs_path = normalize_path(raw_path)
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
