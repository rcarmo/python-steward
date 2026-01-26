"""skill tool - discover and load skills from SKILL.md files."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

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


@dataclass
class SkillMetadata:
    """Parsed skill metadata from SKILL.md."""
    name: str
    description: str
    license: Optional[str] = None
    body: str = ""
    path: str = ""


def parse_frontmatter(content: str) -> tuple[Dict[str, str], str]:
    """Parse YAML frontmatter from content. Returns (frontmatter_dict, remaining_content)."""
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    frontmatter_text = content[3:end_match.start() + 3]
    remaining = content[end_match.end() + 3:]

    # Simple YAML parsing (key: value pairs)
    frontmatter: Dict[str, str] = {}
    for line in frontmatter_text.strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()

    return frontmatter, remaining


def parse_skill(content: str, path: str = "") -> SkillMetadata:
    """Parse SKILL.md and return structured metadata."""
    frontmatter, body = parse_frontmatter(content)

    # Get name from frontmatter or first heading
    name = frontmatter.get("name", "")
    if not name:
        for line in body.split("\n"):
            if line.startswith("# "):
                name = line[2:].strip()
                break
        if not name:
            name = "Unknown Skill"

    # Get description from frontmatter or first paragraph
    description = frontmatter.get("description", "")
    if not description:
        lines = body.strip().split("\n")
        for i, line in enumerate(lines):
            # Skip title line
            if line.startswith("# "):
                continue
            # First non-empty, non-heading line is description
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped[:500]
                break

    return SkillMetadata(
        name=name,
        description=description,
        license=frontmatter.get("license"),
        body=body.strip(),
        path=path,
    )


def format_skill_output(skill: SkillMetadata) -> str:
    """Format skill metadata for output."""
    lines = [f"# {skill.name}"]

    if skill.description:
        lines.append(f"\n{skill.description}")

    if skill.license:
        lines.append(f"\n**License:** {skill.license}")

    # Extract key sections from body
    sections = extract_sections(skill.body)

    for key in ["overview", "core capabilities", "capabilities", "tools", "commands", "skills", "process"]:
        if key in sections:
            content = sections[key][:1000]
            lines.append(f"\n## {key.title()}\n{content}")

    for key in ["usage", "usage modes", "examples"]:
        if key in sections:
            content = sections[key][:500]
            lines.append(f"\n## {key.title()}\n{content}")

    return "\n".join(lines)


def extract_sections(body: str) -> Dict[str, str]:
    """Extract ## sections from markdown body."""
    sections: Dict[str, List[str]] = {}
    current_section = "description"
    sections[current_section] = []

    for line in body.split("\n"):
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            sections[current_section] = []
        elif current_section:
            sections.setdefault(current_section, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


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
    skill = parse_skill(content, rel_path(abs_path))
    output = format_skill_output(skill)

    return {
        "id": "load_skill",
        "output": f"Loaded skill from {rel_path(abs_path)}:\n\n{output}",
    }
