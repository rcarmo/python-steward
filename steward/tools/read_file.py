"""read_file tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, env_cap, normalize_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "read_file",
    "description": "Read file content with optional line range",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "startLine": {"type": "number"},
            "endLine": {"type": "number"},
            "maxLines": {"type": "number"},
            "maxBytes": {"type": "number"},
        },
        "required": ["path"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("'path' must be a string")
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path)

    start_line = args.get("startLine") if isinstance(args.get("startLine"), int) else 1
    end_line = args.get("endLine") if isinstance(args.get("endLine"), int) else None
    max_lines = args.get("maxLines") if isinstance(args.get("maxLines"), int) else env_cap("STEWARD_READ_MAX_LINES", 200)
    max_bytes = args.get("maxBytes") if isinstance(args.get("maxBytes"), int) else env_cap("STEWARD_READ_MAX_BYTES", 16000)

    contents = abs_path.read_text(encoding="utf8")
    limited = contents.encode("utf8")[:max_bytes].decode("utf8", errors="ignore")
    lines = limited.splitlines()
    slice_end = end_line if end_line is not None else start_line - 1 + max_lines
    selection = lines[start_line - 1 : slice_end]
    segment = "\n".join(selection)
    truncated_bytes = len(contents.encode("utf8")) > len(limited.encode("utf8"))
    truncated_lines = end_line is None and len(selection) >= max_lines
    note = "\n[truncated]" if truncated_bytes or truncated_lines else ""
    from_line = start_line
    to_line = end_line if end_line is not None else start_line - 1 + len(selection)
    return {"id": "read", "output": f"Lines {from_line}-{to_line}:\n{segment}{note}"}
