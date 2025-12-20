"""grep_search tool."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import (
    build_matcher,
    env_cap,
    ensure_inside_workspace,
    is_binary_buffer,
    is_hidden,
    normalize_path,
    rel_path,
    walk,
)

TOOL_DEFINITION: ToolDefinition = {
    "name": "grep_search",
    "description": "Search for a pattern in workspace files",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
            "regex": {"type": "boolean"},
            "includePath": {"type": "string"},
            "excludePath": {"type": "string"},
            "includeGlob": {"type": "string"},
            "excludeGlob": {"type": "string"},
            "maxResults": {"type": "number"},
            "contextLines": {"type": "number"},
            "caseSensitive": {"type": "boolean"},
            "smartCase": {"type": "boolean"},
            "fixedString": {"type": "boolean"},
            "wordMatch": {"type": "boolean"},
            "includeHidden": {"type": "boolean"},
            "includeBinary": {"type": "boolean"},
            "maxFileBytes": {"type": "number"},
            "withContextLabels": {"type": "boolean"},
            "withContextSeparators": {"type": "boolean"},
            "beforeContext": {"type": "number"},
            "afterContext": {"type": "number"},
            "withHeadings": {"type": "boolean"},
            "withCounts": {"type": "boolean"},
        },
        "required": ["pattern"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    pattern = args.get("pattern")
    if not isinstance(pattern, str):
        raise ValueError("'pattern' must be a string")

    root = normalize_path(args.get("path") if isinstance(args.get("path"), str) else ".")
    ensure_inside_workspace(root)

    is_regex = args.get("regex") is True
    include_path_re = re.compile(args.get("includePath"), re.IGNORECASE) if isinstance(args.get("includePath"), str) else None
    exclude_path_re = re.compile(args.get("excludePath"), re.IGNORECASE) if isinstance(args.get("excludePath"), str) else None
    include_glob = args.get("includeGlob") if isinstance(args.get("includeGlob"), str) else None
    exclude_glob = args.get("excludeGlob") if isinstance(args.get("excludeGlob"), str) else None

    max_results = args.get("maxResults") if isinstance(args.get("maxResults"), int) else env_cap("STEWARD_SEARCH_MAX_RESULTS", 80)
    context_lines = args.get("contextLines") if isinstance(args.get("contextLines"), int) else 0
    before_context = args.get("beforeContext") if isinstance(args.get("beforeContext"), int) else context_lines
    after_context = args.get("afterContext") if isinstance(args.get("afterContext"), int) else context_lines
    case_sensitive = args.get("caseSensitive") is True
    smart_case = args.get("smartCase") is True
    fixed_string = args.get("fixedString") is True
    word_match = args.get("wordMatch") is True
    include_hidden = args.get("includeHidden") is True
    include_binary = args.get("includeBinary") is True
    max_file_bytes = args.get("maxFileBytes") if isinstance(args.get("maxFileBytes"), int) else env_cap("STEWARD_SEARCH_MAX_FILE_BYTES", 512000)
    with_context_labels = args.get("withContextLabels") is True
    with_context_separators = args.get("withContextSeparators") is True
    with_headings = args.get("withHeadings") is True
    with_counts = args.get("withCounts") is True

    matcher = build_matcher(
        pattern,
        is_regex=is_regex,
        case_sensitive=case_sensitive,
        smart_case=smart_case,
        fixed_string=fixed_string,
        word_match=word_match,
    )

    matches: List[str] = []
    per_file: dict[str, dict] = {}

    def limit_reached() -> bool:
        return len(matches) >= max_results

    def visit(file_path: Path) -> None:
        if limit_reached():
            return
        rel = rel_path(file_path)
        if include_glob and not fnmatch.fnmatch(rel, include_glob):
            return
        if exclude_glob and fnmatch.fnmatch(rel, exclude_glob):
            return
        if include_path_re and not include_path_re.search(str(file_path)):
            return
        if exclude_path_re and exclude_path_re.search(str(file_path)):
            return
        if not include_hidden and is_hidden(rel):
            return
        try:
            data = file_path.read_bytes()
        except OSError:
            return
        if len(data) > max_file_bytes:
            return
        if not include_binary and is_binary_buffer(data):
            return
        text = data.decode("utf8", errors="ignore")
        lines = text.splitlines()
        record = per_file.setdefault(rel, {"lines": [], "match_count": 0, "last": None})
        for idx, line in enumerate(lines):
            if limit_reached():
                break
            if matcher(line):
                record["match_count"] += 1
                start = max(0, idx - before_context)
                end = min(len(lines), idx + after_context + 1)
                needs_sep = with_context_separators and record["last"] is not None and start > record["last"]
                if needs_sep:
                    matches.append("--")
                    record["lines"].append("--")
                for ctx_idx in range(start, end):
                    if record["last"] is not None and ctx_idx <= record["last"]:
                        continue
                    tag = ""
                    if with_context_labels:
                        tag = "M: " if ctx_idx == idx else "C: "
                    entry = f"{rel}:{ctx_idx + 1}: {tag}{lines[ctx_idx].strip()}"
                    matches.append(entry)
                    record["lines"].append(entry)
                record["last"] = end - 1

    walk(root, visit, limit_reached)

    if not matches:
        return {"id": "search", "output": "No matches"}

    if with_headings or with_counts:
        grouped: List[str] = []
        for file_name, record in per_file.items():
            if not record["lines"]:
                continue
            heading = file_name
            if with_counts:
                count = record["match_count"]
                heading = f"{file_name} ({count} match{'es' if count != 1 else ''})"
            grouped.append(heading)
            grouped.extend(record["lines"])
        return {"id": "search", "output": "\n".join(grouped)}

    return {"id": "search", "output": "\n".join(matches)}
