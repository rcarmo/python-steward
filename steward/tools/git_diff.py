"""git_diff tool."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, run_captured, truncate_output


def tool_git_diff(
    path: Optional[str] = None,
    file: Optional[str] = None,
    ref: Optional[str] = None,
    staged: bool = False,
) -> ToolResult:
    """Show git diff output. Can show staged changes, specific files, or compare refs.

    Args:
        path: Working directory for git command (default: current directory)
        file: Specific file to diff
        ref: Git ref (branch, commit, tag) to diff against
        staged: If true, show staged (cached) changes only
    """
    cwd = normalize_path(path) if path else Path.cwd()
    ensure_inside_workspace(cwd)
    cmd: List[str] = ["git", "diff"]
    if staged:
        cmd.append("--cached")
    if ref:
        cmd.append(ref)
    if file:
        cmd.extend(["--", file])
    exit_code, stdout, stderr = run_captured(cmd, cwd)
    stderr_part = "\nstderr:\n" + stderr if stderr else ""
    body = f"exit {exit_code}\n{stdout}{stderr_part}"
    return {"id": "git_diff", "output": truncate_output(body, 24000), "next_tool": ["edit", "git_commit"]}
