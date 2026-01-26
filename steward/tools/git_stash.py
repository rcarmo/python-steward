"""git_stash tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "git_stash",
    "description": "Manage git stash (save/pop/list)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "action": {"type": "string", "enum": ["save", "push", "pop", "list"]},
            "message": {"type": "string"},
        },
    },
}


def tool_handler(args: Dict) -> ToolResult:
    cwd = normalize_path(args.get("path")) if isinstance(args.get("path"), str) else Path.cwd()
    action = args.get("action") if isinstance(args.get("action"), str) else "save"
    message = args.get("message") if isinstance(args.get("message"), str) else None
    ensure_inside_workspace(cwd)
    if action in {"save", "push"}:
        cmd: List[str] = ["git", "stash", "push"]
        if message:
            cmd.extend(["-m", message])
    elif action == "pop":
        cmd = ["git", "stash", "pop"]
    elif action == "list":
        cmd = ["git", "stash", "list"]
    else:
        raise ValueError("Unsupported stash action")
    exit_code, stdout, stderr = run_captured(cmd, cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_stash", "output": truncate_output(body, 16000)}
