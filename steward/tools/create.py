"""create tool - create new files (aligned with Copilot CLI)."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "create",
    "description": "Create a new file with specified content. Cannot be used if the file already exists. Parent directories must exist or will be created.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Full path to file to create. File must not already exist.",
            },
            "file_text": {
                "type": "string",
                "description": "The content of the file to be created.",
            },
        },
        "required": ["path"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    file_text = args.get("file_text") if isinstance(args.get("file_text"), str) else ""
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path, must_exist=False)
    if abs_path.exists():
        raise ValueError(f"File already exists: {rel_path(abs_path)}. Use edit tool to modify existing files.")
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(file_text, encoding="utf8")
    return {"id": "create", "output": f"Created file {rel_path(abs_path)} with {len(file_text)} characters"}
