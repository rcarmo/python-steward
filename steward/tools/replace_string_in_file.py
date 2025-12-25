"""replace_string_in_file tool."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "replace_string_in_file",
    "description": "Replace exact string match in a file with new content",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "oldString": {"type": "string"},
            "newString": {"type": "string"},
        },
        "required": ["path", "oldString", "newString"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    old_string = args.get("oldString")
    new_string = args.get("newString")
    
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")
    if not isinstance(old_string, str):
        raise ValueError("'oldString' must be a string")
    if not isinstance(new_string, str):
        raise ValueError("'newString' must be a string")
    
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path, must_exist=False)
    
    if not abs_path.exists():
        raise ValueError(f"File does not exist: {rel_path(abs_path)}")
    
    content = abs_path.read_text(encoding="utf8")
    
    if old_string not in content:
        raise ValueError(f"String not found in {rel_path(abs_path)}")
    
    occurrences = content.count(old_string)
    if occurrences > 1:
        raise ValueError(f"String appears {occurrences} times in {rel_path(abs_path)}; must be unique")
    
    new_content = content.replace(old_string, new_string, 1)
    abs_path.write_text(new_content, encoding="utf8")
    
    return {"id": "replace_string_in_file", "output": f"Replaced 1 occurrence in {rel_path(abs_path)}"}
