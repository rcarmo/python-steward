"""create_file tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "create_file",
    "description": "Create or overwrite a file with content",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "overwrite": {"type": "boolean"},
        },
        "required": ["path"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    content = args.get("content") if isinstance(args.get("content"), str) else ""
    overwrite = args.get("overwrite") is True
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path, must_exist=False)
    if abs_path.exists() and not overwrite:
        raise ValueError("File exists; set overwrite true to replace")
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf8")
    return {"id": "create_file", "output": f"Created {rel_path(abs_path)}"}
