"""git_commit tool."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output


def tool_git_commit(message: str, path: Optional[str] = None, all: bool = False) -> ToolResult:
    """Commit staged changes.

    Args:
        message: Commit message
        path: Working directory for git command (default: current directory)
        all: If true, automatically stage all modified/deleted files
    """
    cwd = normalize_path(path) if path else Path.cwd()
    ensure_inside_workspace(cwd)
    cmd: List[str] = ["git", "commit"]
    if all:
        cmd.append("--all")
    cmd.extend(["-m", message])
    exit_code, stdout, stderr = run_captured(cmd, cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_commit", "output": truncate_output(body, 16000), "next_tool": ["git_status"]}
