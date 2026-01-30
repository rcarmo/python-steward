"""git_stash tool."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output


def tool_git_stash(
    path: Optional[str] = None,
    action: str = "save",
    message: Optional[str] = None,
) -> ToolResult:
    """Manage git stash: save, pop, or list stashed changes.

    Args:
        path: Working directory for git command (default: current directory)
        action: Stash action: save/push, pop, or list (default: save)
        message: Message for stash save/push
    """
    cwd = normalize_path(path) if path else Path.cwd()
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
