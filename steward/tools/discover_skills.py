"""discover_skills tool - find all SKILL.md files in workspace."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "discover_skills",
    "description": "Find all SKILL.md files in the workspace. Returns paths to skill definitions that can be loaded with load_skill.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to search in. Defaults to current directory.",
            },
        },
    },
}

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path") if isinstance(args.get("path"), str) else "."
    root = Path.cwd() / raw_path

    if not root.is_dir():
        return {"id": "discover_skills", "output": f"Not a directory: {raw_path}"}

    skills: List[str] = []

    def search(directory: Path, depth: int = 0) -> None:
        if depth > 5:  # Max depth
            return
        try:
            for entry in directory.iterdir():
                if entry.name in IGNORED_DIRS:
                    continue
                if entry.name.startswith(".") and entry.name != ".":
                    continue
                if entry.is_file() and entry.name.lower() == "skill.md":
                    skills.append(rel_path(entry))
                elif entry.is_dir():
                    search(entry, depth + 1)
        except PermissionError:
            pass

    search(root)

    if not skills:
        return {"id": "discover_skills", "output": "No SKILL.md files found in workspace"}

    output = f"Found {len(skills)} skill(s):\n\n"
    for skill_path in sorted(skills):
        output += f"- {skill_path}\n"
    output += "\nUse load_skill to read skill details."

    return {"id": "discover_skills", "output": output}
