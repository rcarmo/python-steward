"""get_changed_files tool."""

from __future__ import annotations

import subprocess
from typing import Dict, List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def parse_status_lines(lines: List[str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {"staged": [], "unstaged": [], "untracked": [], "merge-conflicts": []}
    for raw in lines:
        line = raw.rstrip("\n")
        if not line or line.startswith("##"):
            continue
        if line.startswith("??"):
            buckets["untracked"].append(line[3:])
            continue
        if len(line) < 3:
            continue
        x_status, y_status, path = line[0], line[1], line[3:]
        if "U" in (x_status, y_status):
            buckets["merge-conflicts"].append(path)
            continue
        if x_status != " ":
            buckets["staged"].append(path)
        if y_status != " ":
            buckets["unstaged"].append(path)
    return buckets


def tool_get_changed_files(
    repositoryPath: Optional[str] = None,
    sourceControlState: Optional[List[str]] = None,
) -> ToolResult:
    """List git changes grouped by state (staged, unstaged, untracked, merge-conflicts).

    Args:
        repositoryPath: Path to git repository (default: current directory)
        sourceControlState: Filter by change states (default: all states)
    """
    repo_path = normalize_path(repositoryPath) if repositoryPath else normalize_path(".")
    ensure_inside_workspace(repo_path, must_exist=True)
    if not (repo_path / ".git").exists():
        raise ValueError("Not a git repository")

    proc = subprocess.run(
        ["git", "status", "--porcelain=1", "--branch"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    lines = proc.stdout.splitlines()
    buckets = parse_status_lines(lines)

    desired = set(sourceControlState) if sourceControlState else set(buckets.keys())
    output_lines: List[str] = []
    for key in ("staged", "unstaged", "untracked", "merge-conflicts"):
        if key not in desired:
            continue
        for item in buckets[key]:
            abs_item = (repo_path / item).resolve()
            try:
                ensure_inside_workspace(abs_item, must_exist=True)
            except ValueError:
                continue
            output_lines.append(f"{key}: {rel_path(abs_item)}")

    return {"id": "get_changed_files", "output": "\n".join(output_lines), "next_tool": ["git_diff", "view"]}
