"""file_search tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "file_search",
    "description": "Search for files by glob pattern (workspace-relative)",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "maxResults": {"type": "number"},
        },
        "required": ["query"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    query = args.get("query") if isinstance(args.get("query"), str) else None
    max_results = args.get("maxResults") if isinstance(args.get("maxResults"), int) else 200
    if not query:
        raise ValueError("'query' must be a string")

    root = Path.cwd()
    results: List[str] = []
    for match in root.glob(query):
        abs_path = match.resolve()
        ensure_inside_workspace(abs_path, must_exist=True)
        results.append(f"{rel_path(abs_path)}{'/' if abs_path.is_dir() else ''}")
        if len(results) >= max_results:
            break

    return {"id": "file_search", "output": "\n".join(results)}
