"""list_code_usages tool."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, is_binary_buffer, rel_path


def iter_targets(file_paths: Optional[List[str]]) -> Iterable[Path]:
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


def tool_list_code_usages(
    symbolName: str,
    filePaths: Optional[List[str]] = None,
    maxResults: int = 200,
) -> ToolResult:
    """Find all occurrences of a symbol/identifier across files.

    Args:
        symbolName: The symbol/identifier name to search for
        filePaths: List of file or directory paths to search (default: current directory)
        maxResults: Maximum number of results to return (default: 200)
    """
    pattern = re.compile(rf"\b{re.escape(symbolName)}\b")
    matches: List[str] = []

    for target in iter_targets(filePaths):
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
                    if len(matches) >= maxResults:
                        return {"id": "list_code_usages", "output": "\n".join(matches)}

    return {"id": "list_code_usages", "output": "\n".join(matches)}
