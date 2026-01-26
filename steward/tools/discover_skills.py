"""discover_skills tool - find all SKILL.md files in workspace."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..skills import get_registry
from ..types import ToolDefinition, ToolResult
from .shared import rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "discover_skills",
    "description": "Find all SKILL.md files in the workspace. Returns paths and metadata for skill definitions that can be loaded with load_skill.",
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

    registry = get_registry()
    registry.discover(root)

    skills: List[Dict[str, str]] = []
    for skill in registry.all():
        skill_info = {"path": skill.path or rel_path(root / "SKILL.md")}
        if skill.name:
            skill_info["name"] = skill.name
        if skill.description:
            skill_info["description"] = skill.description[:200]
        skills.append(skill_info)

    if not skills:
        return {"id": "discover_skills", "output": "No SKILL.md files found in workspace"}

    output = f"Found {len(skills)} skill(s):\n\n"
    for skill in sorted(skills, key=lambda s: s["path"]):
        output += f"- **{skill['path']}**"
        if skill.get("name"):
            output += f" ({skill['name']})"
        output += "\n"
        if skill.get("description"):
            output += f"  {skill['description']}\n"
    output += "\nUse load_skill to read full skill details."

    return {"id": "discover_skills", "output": output}
