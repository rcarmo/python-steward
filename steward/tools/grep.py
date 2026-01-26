"""grep tool - search file contents using ripgrep-style options (aligned with Copilot CLI)."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import (
    ensure_inside_workspace,
    env_cap,
    is_binary_buffer,
    is_hidden,
    normalize_path,
    rel_path,
    walk,
)

TOOL_DEFINITION: ToolDefinition = {
    "name": "grep",
    "description": "Search file contents for a regex pattern. REQUIRED: pattern (string). Returns matching files or lines.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "REQUIRED. The regex pattern to search for. Must be a non-empty string.",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in. Defaults to current working directory.",
            },
            "glob": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.js', '*.{ts,tsx}').",
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_with_matches", "count"],
                "description": "Output format: 'content' shows matching lines, 'files_with_matches' shows only paths, 'count' shows match counts per file.",
            },
            "-i": {
                "type": "boolean",
                "description": "Case insensitive search.",
            },
            "-n": {
                "type": "boolean",
                "description": "Show line numbers (requires output_mode: 'content').",
            },
            "-A": {
                "type": "number",
                "description": "Lines of context after match.",
            },
            "-B": {
                "type": "number",
                "description": "Lines of context before match.",
            },
            "-C": {
                "type": "number",
                "description": "Lines of context before and after match.",
            },
            "head_limit": {
                "type": "number",
                "description": "Limit output to first N results.",
            },
            "multiline": {
                "type": "boolean",
                "description": "Enable multiline mode where patterns can span lines.",
            },
        },
        "required": ["pattern"],
    },
}

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


def tool_handler(args: Dict) -> ToolResult:
    pattern = args.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return {"id": "grep", "output": "Error: 'pattern' is required and must be a non-empty string", "error": True}

    root = normalize_path(args.get("path") if isinstance(args.get("path"), str) else ".")
    ensure_inside_workspace(root)

    glob_pattern = args.get("glob") if isinstance(args.get("glob"), str) else None
    output_mode = args.get("output_mode", "files_with_matches")
    case_insensitive = args.get("-i") is True
    show_line_numbers = args.get("-n") is True
    context_after = args.get("-A") if isinstance(args.get("-A"), int) else 0
    context_before = args.get("-B") if isinstance(args.get("-B"), int) else 0
    context_both = args.get("-C") if isinstance(args.get("-C"), int) else 0
    head_limit = args.get("head_limit") if isinstance(args.get("head_limit"), int) else env_cap("STEWARD_SEARCH_MAX_RESULTS", 100)
    multiline = args.get("multiline") is True

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
        return result_count >= head_limit

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
        except OSError:
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
        output = "\n".join(files_with_matches[:head_limit])
    elif output_mode == "count":
        output = "\n".join(f"{f}:{c}" for f, c in list(file_counts.items())[:head_limit])
    else:  # content
        output = "\n".join(results)

    if not output:
        return {"id": "grep", "output": "No matches found"}

    return {"id": "grep", "output": output}
