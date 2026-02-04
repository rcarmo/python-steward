"""skill tool - discover and load skills from SKILL.md files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


@dataclass
class SkillMetadata:
    """Parsed skill metadata from SKILL.md."""

    name: str
    description: str
    license: Optional[str] = None
    triggers: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    chain: List[str] = field(default_factory=list)
    body: str = ""
    path: str = ""
    frontmatter: Dict[str, str | List[str]] = field(default_factory=dict)
    content: str = ""


def parse_frontmatter(content: str) -> tuple[Dict[str, str | List[str]], str]:
    """Parse YAML frontmatter from content. Returns (frontmatter_dict, remaining_content)."""
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    frontmatter_text = content[3 : end_match.start() + 3]
    remaining = content[end_match.end() + 3 :]

    # Simple YAML parsing (key: value pairs and lists)
    frontmatter: Dict[str, str | List[str]] = {}
    current_key: Optional[str] = None
    current_list: List[str] = []

    for line in frontmatter_text.strip().split("\n"):
        # Check for list item
        if line.strip().startswith("- ") and current_key:
            current_list.append(line.strip()[2:].strip())
            continue

        # If we were building a list, save it
        if current_list and current_key:
            frontmatter[current_key] = current_list
            current_list = []
            current_key = None

        # Check for key: value
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                frontmatter[key] = value
            else:
                # Start of a list
                current_key = key

    # Save any remaining list
    if current_list and current_key:
        frontmatter[current_key] = current_list

    return frontmatter, remaining


def _parse_list_field(value: object) -> List[str]:
    """Parse a frontmatter field into a list of non-empty strings."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if item is not None and str(item).strip()]
    return []


def parse_skill(content: str, path: str = "") -> SkillMetadata:
    """Parse SKILL.md and return structured metadata."""
    frontmatter, body = parse_frontmatter(content)

    # Get name from frontmatter or first heading
    name = frontmatter.get("name", "")
    if not name or not isinstance(name, str):
        name = ""
        for line in body.split("\n"):
            if line.startswith("# "):
                name = line[2:].strip()
                break
        if not name:
            name = "Unknown Skill"

    # Get description from frontmatter or first paragraph
    description = frontmatter.get("description", "")
    if not description or not isinstance(description, str):
        description = ""
        lines = body.strip().split("\n")
        for line in lines:
            if line.startswith("# "):
                continue
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped[:500]
                break
    # Ensure description is always a string
    if description is None:
        description = ""

    # Parse list fields (safely handles None values and non-list types)
    triggers = _parse_list_field(frontmatter.get("triggers", []))
    requires = _parse_list_field(frontmatter.get("requires", []))
    chain = _parse_list_field(frontmatter.get("chain", []))

    license_val = frontmatter.get("license")
    if not isinstance(license_val, str):
        license_val = None

    return SkillMetadata(
        name=name,
        description=description,
        license=license_val,
        triggers=triggers,
        requires=requires,
        chain=chain,
        body=body.strip(),
        path=path,
        frontmatter=frontmatter,
        content=content,
    )


def format_skill_output(skill: SkillMetadata) -> str:
    """Format skill metadata for output."""
    lines = [f"# {skill.name}"]

    if skill.description:
        lines.append(f"\n{skill.description}")

    # Metadata section
    meta_parts = []
    if skill.license:
        meta_parts.append(f"**License:** {skill.license}")
    if skill.triggers:
        meta_parts.append(f"**Triggers:** {', '.join(skill.triggers)}")
    if skill.requires:
        meta_parts.append(f"**Requires:** {', '.join(skill.requires)}")
    if skill.chain:
        meta_parts.append(f"**Chain:** {', '.join(skill.chain)}")
    if meta_parts:
        lines.append("\n" + " | ".join(meta_parts))

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


def tool_load_skill(path: Optional[str] = None) -> ToolResult:
    """Load a skill definition from a SKILL.md file.

    Args:
        path: Path to SKILL.md file, or directory containing SKILL.md (default: current directory)
    """
    raw_path = path if path else "."
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
