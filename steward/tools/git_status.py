"""git_status tool."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output


def tool_handler(path: Optional[str] = None) -> ToolResult:
    """Show git status (short format) for the workspace or a subdirectory.

    Args:
        path: Directory path to check status (default: current directory)
    """
    cwd = normalize_path(path) if path else Path.cwd()
    ensure_inside_workspace(cwd)
    exit_code, stdout, stderr = run_captured(["git", "status", "--short", "--branch"], cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_status", "output": truncate_output(body, 16000)}
