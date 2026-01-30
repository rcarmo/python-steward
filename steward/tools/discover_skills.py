"""discover_skills tool - find all SKILL.md files in workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from ..skills import get_registry
from ..types import ToolResult
from .shared import rel_path

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}


def tool_discover_skills(path: Optional[str] = None) -> ToolResult:
    """Find all SKILL.md files in the workspace.

    Args:
        path: Directory to search in (default: current directory)
    """
    root = Path.cwd() / (path if path else ".")

    if not root.is_dir():
        return {"id": "discover_skills", "output": f"Not a directory: {path or '.'}"}

    registry = get_registry()
    registry.discover(root)

    skills: List[Dict[str, str]] = []
    for skill in registry.all():
        skill_info: Dict[str, str] = {"path": skill.path or rel_path(root / "SKILL.md")}
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
