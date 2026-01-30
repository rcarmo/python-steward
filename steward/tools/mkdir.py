"""mkdir tool - create directories (aligned with Copilot CLI behavior)."""

from __future__ import annotations

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def tool_mkdir(path: str) -> ToolResult:
    """Create a directory. Parent directories are created automatically if needed.

    Args:
        path: Path to directory to create
    """
    abs_path = normalize_path(path)
    ensure_inside_workspace(abs_path, must_exist=False)

    if abs_path.exists():
        if abs_path.is_dir():
            return {"id": "mkdir", "output": f"Directory already exists: {rel_path(abs_path)}"}
        else:
            raise ValueError(f"Path exists but is not a directory: {rel_path(abs_path)}")

    abs_path.mkdir(parents=True, exist_ok=True)
    return {"id": "mkdir", "output": f"Created directory: {rel_path(abs_path)}"}
