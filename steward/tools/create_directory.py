"""create_directory tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "create_directory",
    "description": "Create a directory (parents optional)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "parents": {"type": "boolean"},
            "existOk": {"type": "boolean"},
        },
        "required": ["path"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    parents = args.get("parents") is not False
    exist_ok = args.get("existOk") is True
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path, must_exist=False)
    Path(abs_path).mkdir(parents=parents, exist_ok=exist_ok)
    return {"id": "create_directory", "output": f"Created {rel_path(abs_path)}"}
