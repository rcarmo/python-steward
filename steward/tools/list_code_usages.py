"""list_code_usages tool."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, is_binary_buffer, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "list_code_usages",
    "description": "Find all occurrences of a symbol/identifier across files. REQUIRED: symbolName (string).",
    "parameters": {
        "type": "object",
        "properties": {
            "symbolName": {
                "type": "string",
                "description": "REQUIRED. The symbol/identifier name to search for.",
            },
            "filePaths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional. List of file or directory paths to search. Defaults to current directory.",
            },
            "maxResults": {
                "type": "number",
                "description": "Optional. Maximum number of results to return.",
            },
        },
        "required": ["symbolName"],
    },
}


def iter_targets(file_paths: List[str] | None) -> Iterable[Path]:
    if not file_paths:
        yield Path.cwd()
        return
    for raw in file_paths:
        path = Path.cwd() / raw
        ensure_inside_workspace(path, must_exist=True)
        yield path.resolve()


def iter_files(target: Path) -> Iterable[Path]:
    if target.is_file():
        yield target
    elif target.is_dir():
        skip = {"node_modules", ".git"}
        for entry in target.rglob("*"):
            if any(part in skip for part in entry.parts):
                continue
            if entry.is_file():
                yield entry


def tool_handler(args: Dict) -> ToolResult:
    symbol = args.get("symbolName") if isinstance(args.get("symbolName"), str) else None
    file_paths = args.get("filePaths") if isinstance(args.get("filePaths"), list) else None
    max_results = args.get("maxResults") if isinstance(args.get("maxResults"), int) else 200
    if not symbol:
        raise ValueError("'symbolName' must be a string")
    if file_paths is not None and not all(isinstance(p, str) for p in file_paths):
        raise ValueError("'filePaths' must be an array of strings")

    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    matches: List[str] = []

    for target in iter_targets(file_paths):
        for file in iter_files(target):
            ensure_inside_workspace(file, must_exist=True)
            try:
                chunk = file.read_bytes()
            except OSError:
                continue
            if is_binary_buffer(chunk[:1024]):
                continue
            try:
                lines = chunk.decode("utf8", errors="ignore").splitlines()
            except UnicodeDecodeError:
                continue
            for idx, line in enumerate(lines, start=1):
                if pattern.search(line):
                    matches.append(f"{rel_path(file)}:{idx}: {line.strip()}")
                    if len(matches) >= max_results:
                        return {"id": "list_code_usages", "output": "\n".join(matches)}

    return {"id": "list_code_usages", "output": "\n".join(matches)}
