"""glob tool - fast file pattern matching (aligned with Copilot CLI)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "glob",
    "description": "Fast file pattern matching using glob patterns. Find files by name patterns.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The glob pattern to match files against (e.g., '**/*.js', 'src/**/*.ts', '*.{ts,tsx}').",
            },
            "path": {
                "type": "string",
                "description": "The directory to search in. Defaults to current working directory.",
            },
        },
        "required": ["pattern"],
    },
}

MAX_RESULTS = 500
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def tool_handler(args: Dict) -> ToolResult:
    pattern = args.get("pattern")
    if not isinstance(pattern, str):
        raise ValueError("'pattern' must be a string")

    search_path = args.get("path") if isinstance(args.get("path"), str) else None
    if search_path:
        root = normalize_path(search_path)
        ensure_inside_workspace(root)
    else:
        root = Path.cwd()

    results: List[str] = []

    # Handle {a,b} brace expansion manually since Python's glob doesn't support it
    patterns = expand_braces(pattern)

    for pat in patterns:
        for match in root.glob(pat):
            # Skip ignored directories
            if any(part in IGNORED_DIRS for part in match.parts):
                continue
            # Skip hidden files/directories
            if any(part.startswith(".") and part != "." for part in match.parts):
                continue

            try:
                abs_path = match.resolve()
                ensure_inside_workspace(abs_path, must_exist=True)
            except (ValueError, OSError):
                continue

            rel = rel_path(abs_path)
            if rel not in results:
                results.append(rel)

            if len(results) >= MAX_RESULTS:
                break

        if len(results) >= MAX_RESULTS:
            break

    if not results:
        return {"id": "glob", "output": "No matching files found"}

    return {"id": "glob", "output": "\n".join(sorted(results))}


def expand_braces(pattern: str) -> List[str]:
    """Expand {a,b,c} patterns into multiple glob patterns."""
    import re

    match = re.search(r"\{([^}]+)\}", pattern)
    if not match:
        return [pattern]

    prefix = pattern[: match.start()]
    suffix = pattern[match.end() :]
    alternatives = match.group(1).split(",")

    expanded = []
    for alt in alternatives:
        expanded.extend(expand_braces(f"{prefix}{alt}{suffix}"))

    return expanded
