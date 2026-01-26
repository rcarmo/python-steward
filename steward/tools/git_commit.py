"""git_commit tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "git_commit",
    "description": "Commit staged changes. REQUIRED: message (string).",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional. Working directory for git command. Defaults to current directory.",
            },
            "message": {
                "type": "string",
                "description": "REQUIRED. Commit message.",
            },
            "all": {
                "type": "boolean",
                "description": "Optional. If true, automatically stage all modified/deleted files (git commit -a).",
            },
        },
        "required": ["message"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    cwd = normalize_path(args.get("path")) if isinstance(args.get("path"), str) else Path.cwd()
    message = args.get("message") if isinstance(args.get("message"), str) else None
    all_flag = args.get("all") is True
    if not message:
        raise ValueError("'message' is required")
    ensure_inside_workspace(cwd)
    cmd: List[str] = ["git", "commit"]
    if all_flag:
        cmd.append("--all")
    cmd.extend(["-m", message])
    exit_code, stdout, stderr = run_captured(cmd, cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_commit", "output": truncate_output(body, 16000)}
