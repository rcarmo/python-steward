"""list_dir tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "list_dir",
    "description": "List directory entries (files and subdirectories)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "includeIgnored": {"type": "boolean"},
        },
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path") if isinstance(args.get("path"), str) else "."
    include_ignored = args.get("includeIgnored") is True
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path)
    if not abs_path.is_dir():
        raise ValueError("Path is not a directory")
    entries = list(abs_path.iterdir())
    lines = []
    for entry in entries:
        if not include_ignored and entry.name in {"node_modules", ".git"}:
            continue
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{entry.name}{suffix}")
    return {"id": "list_dir", "output": "\n".join(lines)}
