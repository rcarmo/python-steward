"""mkdir tool - create directories (aligned with Copilot CLI behavior)."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "mkdir",
    "description": "Create a directory. Parent directories are created automatically if they don't exist.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to directory to create.",
            },
        },
        "required": ["path"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")

    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path, must_exist=False)

    if abs_path.exists():
        if abs_path.is_dir():
            return {"id": "mkdir", "output": f"Directory already exists: {rel_path(abs_path)}"}
        else:
            raise ValueError(f"Path exists but is not a directory: {rel_path(abs_path)}")

    abs_path.mkdir(parents=True, exist_ok=True)
    return {"id": "mkdir", "output": f"Created directory: {rel_path(abs_path)}"}
