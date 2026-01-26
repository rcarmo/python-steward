"""git_diff tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "git_diff",
    "description": "Show git diff (optionally staged or for a path/ref)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "file": {"type": "string"},
            "ref": {"type": "string"},
            "staged": {"type": "boolean"},
        },
    },
}


def tool_handler(args: Dict) -> ToolResult:
    cwd = normalize_path(args.get("path")) if isinstance(args.get("path"), str) else Path.cwd()
    file_arg = args.get("file") if isinstance(args.get("file"), str) else None
    ref = args.get("ref") if isinstance(args.get("ref"), str) else None
    staged = args.get("staged") is True
    ensure_inside_workspace(cwd)
    cmd: List[str] = ["git", "diff"]
    if staged:
        cmd.append("--cached")
    if ref:
        cmd.append(ref)
    if file_arg:
        cmd.extend(["--", file_arg])
    exit_code, stdout, stderr = run_captured(cmd, cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_diff", "output": truncate_output(body, 24000)}
