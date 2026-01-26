"""skill tool - discover and load skills from SKILL.md files."""
from __future__ import annotations

from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "load_skill",
    "description": "Load a skill definition from a SKILL.md file. Use to discover capabilities of tools, agents, or projects in the workspace.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to SKILL.md file, or directory containing SKILL.md. Defaults to current directory.",
            },
        },
    },
}


def tool_handler(args: Dict) -> ToolResult:
    raw_path = args.get("path") if isinstance(args.get("path"), str) else "."
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path)

    # If path is a directory, look for SKILL.md inside it
    if abs_path.is_dir():
        skill_file = abs_path / "SKILL.md"
        if not skill_file.exists():
            # Try lowercase
            skill_file = abs_path / "skill.md"
        if not skill_file.exists():
            return {"id": "load_skill", "output": f"No SKILL.md found in {rel_path(abs_path)}"}
        abs_path = skill_file

    if not abs_path.is_file():
        return {"id": "load_skill", "output": f"File not found: {rel_path(abs_path)}"}

    content = abs_path.read_text(encoding="utf8")
    parsed = parse_skill(content)

    return {
        "id": "load_skill",
        "output": f"Loaded skill from {rel_path(abs_path)}:\n\n{parsed}",
    }


def parse_skill(content: str) -> str:
    """Parse SKILL.md and return structured summary."""
    lines = content.strip().split("\n")

    # Extract title (first # heading)
    title = "Unknown Skill"
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Extract sections
    sections: Dict[str, List[str]] = {}
    current_section = "description"
    sections[current_section] = []

    for line in lines:
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    # Build summary
    output_parts = [f"# {title}"]

    # Get description (content before first ##)
    if sections.get("description"):
        desc = "\n".join(sections["description"]).strip()
        if desc and not desc.startswith("#"):
            output_parts.append(f"\n{desc[:500]}")

    # Extract capabilities/tools if present
    for key in ["core capabilities", "capabilities", "tools", "commands", "skills"]:
        if key in sections:
            content_text = "\n".join(sections[key]).strip()
            if content_text:
                output_parts.append(f"\n## {key.title()}\n{content_text[:1000]}")

    # Extract usage if present
    for key in ["usage", "usage modes", "examples"]:
        if key in sections:
            content_text = "\n".join(sections[key]).strip()
            if content_text:
                output_parts.append(f"\n## {key.title()}\n{content_text[:500]}")

    return "\n".join(output_parts)
