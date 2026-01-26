"""Tests for skills discovery tools."""
from __future__ import annotations

from pathlib import Path


def test_discover_skills_finds_skill_md(tool_handlers, sandbox: Path):
    (sandbox / "SKILL.md").write_text("# Test Skill\n\nDescription here.", encoding="utf8")
    result = tool_handlers["discover_skills"]({})
    assert "Found 1 skill" in result["output"]
    assert "SKILL.md" in result["output"]


def test_discover_skills_recursive(tool_handlers, sandbox: Path):
    subdir = sandbox / "tools" / "mytool"
    subdir.mkdir(parents=True)
    (subdir / "SKILL.md").write_text("# Nested Skill", encoding="utf8")
    (sandbox / "SKILL.md").write_text("# Root Skill", encoding="utf8")
    result = tool_handlers["discover_skills"]({})
    assert "Found 2 skill" in result["output"]


def test_discover_skills_none_found(tool_handlers, sandbox: Path):
    result = tool_handlers["discover_skills"]({})
    assert "No SKILL.md files found" in result["output"]


def test_discover_skills_with_frontmatter(tool_handlers, sandbox: Path):
    skill_content = """---
name: my-skill
description: A test skill for doing things
license: MIT
---

# My Skill

Body content here.
"""
    (sandbox / "SKILL.md").write_text(skill_content, encoding="utf8")
    result = tool_handlers["discover_skills"]({})
    assert "Found 1 skill" in result["output"]
    assert "my-skill" in result["output"]
    assert "A test skill" in result["output"]


def test_load_skill_parses_content(tool_handlers, sandbox: Path):
    skill_content = """# My Tool

A description of the tool.

## Core Capabilities

- Feature 1
- Feature 2

## Usage

```bash
mytool --help
```
"""
    (sandbox / "SKILL.md").write_text(skill_content, encoding="utf8")
    result = tool_handlers["load_skill"]({"path": "."})
    assert "My Tool" in result["output"]
    assert "Feature 1" in result["output"]


def test_load_skill_with_frontmatter(tool_handlers, sandbox: Path):
    skill_content = """---
name: algorithmic-art
description: Creating algorithmic art using p5.js with seeded randomness.
license: MIT
---

# Algorithmic Art Skill

Detailed instructions here.

## Overview

This skill creates generative art.
"""
    (sandbox / "SKILL.md").write_text(skill_content, encoding="utf8")
    result = tool_handlers["load_skill"]({"path": "."})
    assert "algorithmic-art" in result["output"]
    assert "Creating algorithmic art" in result["output"]
    assert "License:** MIT" in result["output"]
    assert "Overview" in result["output"]


def test_load_skill_direct_path(tool_handlers, sandbox: Path):
    (sandbox / "custom.md").write_text("# Custom\n\nCustom skill.", encoding="utf8")
    result = tool_handlers["load_skill"]({"path": "custom.md"})
    assert "Custom" in result["output"]


def test_load_skill_not_found(tool_handlers, sandbox: Path):
    result = tool_handlers["load_skill"]({"path": "."})
    assert "No SKILL.md found" in result["output"]


def test_parse_frontmatter():
    from steward.tools.load_skill import parse_frontmatter

    content = """---
name: test-skill
description: A test description
license: MIT
---

# Body Content
"""
    frontmatter, body = parse_frontmatter(content)
    assert frontmatter["name"] == "test-skill"
    assert frontmatter["description"] == "A test description"
    assert frontmatter["license"] == "MIT"
    assert "Body Content" in body


def test_parse_frontmatter_no_frontmatter():
    from steward.tools.load_skill import parse_frontmatter

    content = "# Just a heading\n\nSome content."
    frontmatter, body = parse_frontmatter(content)
    assert frontmatter == {}
    assert body == content


def test_parse_skill_metadata():
    from steward.tools.load_skill import parse_skill

    content = """---
name: my-skill
description: Skill description from frontmatter
---

# My Skill Title

Body paragraph.
"""
    skill = parse_skill(content, "test/SKILL.md")
    assert skill.name == "my-skill"
    assert skill.description == "Skill description from frontmatter"
    assert skill.path == "test/SKILL.md"


def test_parse_skill_no_frontmatter():
    from steward.tools.load_skill import parse_skill

    content = """# Fallback Title

First paragraph becomes description.

## Section

More content.
"""
    skill = parse_skill(content)
    assert skill.name == "Fallback Title"
    assert "First paragraph" in skill.description
