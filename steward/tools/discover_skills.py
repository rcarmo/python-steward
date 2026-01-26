"""discover_skills tool - find all SKILL.md files in workspace."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .load_skill import parse_frontmatter
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

    skills: List[Dict[str, str]] = []

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
                    skill_info = {"path": rel_path(entry)}
                    # Extract frontmatter metadata
                    try:
                        content = entry.read_text(encoding="utf8")
                        frontmatter, _ = parse_frontmatter(content)
                        if frontmatter.get("name"):
                            skill_info["name"] = frontmatter["name"]
                        if frontmatter.get("description"):
                            skill_info["description"] = frontmatter["description"][:200]
                    except (OSError, IOError):
                        pass
                    skills.append(skill_info)
                elif entry.is_dir():
                    search(entry, depth + 1)
        except PermissionError:
            pass

    search(root)

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
