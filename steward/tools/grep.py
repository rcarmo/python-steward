"""grep tool - search file contents using ripgrep-style options (aligned with Copilot CLI)."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..types import ToolResult
from .shared import (
    ensure_inside_workspace,
    env_cap,
    is_binary_buffer,
    is_hidden,
    normalize_path,
    rel_path,
    walk,
)

# File type to glob mapping (subset of ripgrep types)
TYPE_GLOBS = {
    "js": ["*.js", "*.mjs", "*.cjs"],
    "ts": ["*.ts", "*.tsx"],
    "py": ["*.py"],
    "rust": ["*.rs"],
    "go": ["*.go"],
    "java": ["*.java"],
    "c": ["*.c", "*.h"],
    "cpp": ["*.cpp", "*.cc", "*.cxx", "*.hpp", "*.hh"],
    "json": ["*.json"],
    "yaml": ["*.yaml", "*.yml"],
    "md": ["*.md", "*.markdown"],
    "html": ["*.html", "*.htm"],
    "css": ["*.css", "*.scss", "*.sass", "*.less"],
}


def matches_glob(filename: str, glob_pattern: str) -> bool:
    """Check if filename matches glob pattern, handling {a,b} syntax."""
    if "{" in glob_pattern and "}" in glob_pattern:
        # Expand {a,b} patterns
        match = re.match(r"(.*)\{([^}]+)\}(.*)", glob_pattern)
        if match:
            prefix, alternatives, suffix = match.groups()
            return any(fnmatch.fnmatch(filename, f"{prefix}{alt}{suffix}") for alt in alternatives.split(","))
    return fnmatch.fnmatch(filename, glob_pattern)


def tool_grep(
    pattern: str,
    path: Optional[str] = None,
    glob: Optional[str] = None,
    output_mode: str = "files_with_matches",
    case_insensitive: bool = False,
    show_line_numbers: bool = False,
    context_after: int = 0,
    context_before: int = 0,
    context_both: int = 0,
    head_limit: Optional[int] = None,
    multiline: bool = False,
) -> ToolResult:
    """Search file contents for a regex pattern.

    Args:
        pattern: Regex pattern to search for
        path: File or directory to search (default: current directory)
        glob: Filter files by glob pattern (e.g., '*.js')
        output_mode: 'files_with_matches', 'content', or 'count'
        case_insensitive: Case insensitive search (-i flag)
        show_line_numbers: Show line numbers (-n flag)
        context_after: Lines of context after match (-A flag)
        context_before: Lines of context before match (-B flag)
        context_both: Lines of context before and after (-C flag)
        head_limit: Max number of results
        multiline: Enable multiline pattern matching
    """
    if not pattern:
        return {"id": "grep", "output": "Error: 'pattern' is required and must be a non-empty string", "error": True}

    root = normalize_path(path if path else ".")
    ensure_inside_workspace(root)

    glob_pattern = glob
    limit = head_limit if head_limit is not None else env_cap("STEWARD_SEARCH_MAX_RESULTS", 100)

    if context_both > 0:
        context_before = context_both
        context_after = context_both

    max_file_bytes = env_cap("STEWARD_SEARCH_MAX_FILE_BYTES", 512000)

    # Build matcher
    flags = re.IGNORECASE if case_insensitive else 0
    if multiline:
        flags |= re.MULTILINE | re.DOTALL
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    results: List[str] = []
    file_counts: Dict[str, int] = {}
    files_with_matches: List[str] = []
    result_count = 0

    def limit_reached() -> bool:
        return result_count >= limit

    def visit(file_path: Path) -> None:
        nonlocal result_count
        if limit_reached():
            return

        rel = rel_path(file_path)

        # Apply glob filter
        if glob_pattern and not matches_glob(file_path.name, glob_pattern):
            return

        # Skip hidden files
        if is_hidden(rel):
            return

        try:
            data = file_path.read_bytes()
        except OSError as err:
            files_with_matches.append(f"[error reading {rel}: {err}]")
            return

        if len(data) > max_file_bytes:
            return
        if is_binary_buffer(data):
            return

        text = data.decode("utf8", errors="ignore")
        lines = text.splitlines()

        file_match_count = 0
        matched_line_indices: List[int] = []

        for idx, line in enumerate(lines):
            if regex.search(line):
                file_match_count += 1
                matched_line_indices.append(idx)

        if file_match_count == 0:
            return

        files_with_matches.append(rel)
        file_counts[rel] = file_match_count

        if output_mode == "content" and not limit_reached():
            shown_lines: set = set()
            for idx in matched_line_indices:
                if limit_reached():
                    break
                start = max(0, idx - context_before)
                end = min(len(lines), idx + context_after + 1)
                for i in range(start, end):
                    if i in shown_lines:
                        continue
                    shown_lines.add(i)
                    prefix = f"{rel}:"
                    if show_line_numbers:
                        prefix += f"{i + 1}:"
                    results.append(f"{prefix}{lines[i]}")
                    result_count += 1
                    if limit_reached():
                        break

    walk(root, visit, limit_reached)

    # Format output based on mode
    if output_mode == "files_with_matches":
        output = "\n".join(files_with_matches[:limit])
    elif output_mode == "count":
        output = "\n".join(f"{f}:{c}" for f, c in list(file_counts.items())[:limit])
    else:  # content
        output = "\n".join(results)

    if not output:
        return {"id": "grep", "output": "No matches found", "next_tool": ["glob"]}

    return {"id": "grep", "output": output, "next_tool": ["view", "edit"]}
