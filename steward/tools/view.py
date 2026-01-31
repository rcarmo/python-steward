"""view tool - view files and directories (aligned with Copilot CLI)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, env_cap, normalize_path, rel_path

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def list_directory(dir_path: Path, max_depth: int = 2) -> List[str]:
    """List directory contents up to max_depth levels."""
    entries: List[str] = []

    def walk(current: Path, depth: int, prefix: str = "") -> None:
        if depth > max_depth:
            return
        try:
            items = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError as err:
            entries.append(f"[permission denied: {rel_path(current)}: {err}]")
            return
        for item in items:
            if item.name.startswith(".") and item.name != ".":
                continue
            if item.name in IGNORED_DIRS:
                continue
            rel = rel_path(item)
            if item.is_dir():
                entries.append(f"{rel}/")
                if depth < max_depth:
                    walk(item, depth + 1, prefix + "  ")
            else:
                entries.append(rel)

    walk(dir_path, 1)
    return entries


def tool_view(path: str = ".", view_range: Optional[List[int]] = None) -> ToolResult:
    """View file contents or directory listing.

    Args:
        path: Path to file or directory (default: current directory)
        view_range: [start_line, end_line] for partial file view (use -1 for end)
    """
    abs_path = normalize_path(path)
    ensure_inside_workspace(abs_path)

    # Directory listing
    if abs_path.is_dir():
        entries = list_directory(abs_path)
        return {"id": "view", "output": "\n".join(entries) if entries else "(empty directory)"}

    # File viewing
    if not abs_path.is_file():
        raise ValueError(f"Path does not exist: {rel_path(abs_path)}")

    start_line: int = 1
    end_line: Optional[int] = None

    if isinstance(view_range, list) and len(view_range) >= 2:
        start_line = view_range[0] if isinstance(view_range[0], int) else 1
        end_val = view_range[1]
        end_line = None if end_val == -1 else (end_val if isinstance(end_val, int) else None)

    max_bytes = env_cap("STEWARD_READ_MAX_BYTES", 32000)

    try:
        contents = abs_path.read_text(encoding="utf8")
    except UnicodeDecodeError:
        return {"id": "view", "output": f"(binary file: {rel_path(abs_path)})"}

    # Apply byte limit
    if len(contents.encode("utf8")) > max_bytes:
        contents = contents.encode("utf8")[:max_bytes].decode("utf8", errors="ignore")
        truncated = True
    else:
        truncated = False

    lines = contents.splitlines()
    total_lines = len(lines)

    # Apply line range
    if end_line is None:
        end_line = total_lines
    start_idx = max(0, start_line - 1)
    end_idx = min(total_lines, end_line)
    selected_lines = lines[start_idx:end_idx]

    # Format with line numbers
    output_lines = []
    for i, line in enumerate(selected_lines, start=start_line):
        output_lines.append(f"{i}. {line}")

    result = "\n".join(output_lines)
    if truncated:
        result += "\n[truncated]"

    return {"id": "view", "output": result, "next_tool": ["edit", "grep"]}
