"""workspace_summary tool."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "workspace_summary",
    "description": "Basic workspace summary (package info, top-level dirs/files)",
    "parameters": {"type": "object", "properties": {}},
}


def tool_handler(_: Dict) -> ToolResult:
    root = Path.cwd()
    entries = list(root.iterdir())
    files = [entry.name for entry in entries if entry.is_file() and entry.name not in {".git", "node_modules"}]
    dirs = [entry.name for entry in entries if entry.is_dir() and entry.name not in {".git", "node_modules"}]
    pkg_path = root / "package.json"
    pkg_info = "package: none"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf8"))
            name = pkg.get("name", "unknown")
            version = pkg.get("version", "")
            pkg_info = f"package: {name}@{version}"
        except json.JSONDecodeError:
            pkg_info = "package: none"
    summary = [pkg_info, f"dirs: {', '.join(dirs) if dirs else '-'}", f"files: {', '.join(files) if files else '-'}"]
    return {"id": "workspace_summary", "output": "\n".join(summary)}
