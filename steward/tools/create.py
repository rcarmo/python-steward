"""create tool - create new files (aligned with Copilot CLI)."""
from __future__ import annotations

from typing import Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def tool_create(path: str, file_text: Optional[str] = None) -> ToolResult:
    """Create a new file with specified content. Cannot overwrite existing files.

    Args:
        path: Full path to file to create - must not already exist
        file_text: Content of the file to create (default: empty)
    """
    content = file_text if file_text is not None else ""
    abs_path = normalize_path(path)
    ensure_inside_workspace(abs_path, must_exist=False)
    if abs_path.exists():
        raise ValueError(f"File already exists: {rel_path(abs_path)}. Use edit tool to modify existing files.")
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf8")
    return {"id": "create", "output": f"Created file {rel_path(abs_path)} with {len(content)} characters", "next_tool": ["view", "edit"]}
