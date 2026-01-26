"""git_status tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "git_status",
    "description": "Show git status (short format) for the workspace or a subdirectory.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional. Directory path to check status. Defaults to current directory.",
            },
        },
    },
}


def tool_handler(args: Dict) -> ToolResult:
    cwd = normalize_path(args.get("path")) if isinstance(args.get("path"), str) else Path.cwd()
    ensure_inside_workspace(cwd)
    exit_code, stdout, stderr = run_captured(["git", "status", "--short", "--branch"], cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_status", "output": truncate_output(body, 16000)}
