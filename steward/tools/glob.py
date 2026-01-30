"""glob tool - fast file pattern matching."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

MAX_RESULTS = 500
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def tool_glob(pattern: str, path: Optional[str] = None) -> ToolResult:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern like '**/*.py' or 'src/*.ts'
        path: Directory to search in (default: current directory)
    """
    if not pattern:
        return {"id": "glob", "output": "Error: 'pattern' is required", "error": True}

    if path:
        root = normalize_path(path)
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
        return {"id": "glob", "output": "No matching files found", "next_tool": ["grep"]}

    return {"id": "glob", "output": "\n".join(sorted(results)), "next_tool": ["view", "grep"]}


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
