"""Tests for skills discovery tools."""

from __future__ import annotations

from pathlib import Path

from steward.skills import reset_registry


def test_discover_skills_finds_skill_md(tool_handlers, sandbox: Path):
    reset_registry()
    (sandbox / "SKILL.md").write_text("# Test Skill\n\nDescription here.", encoding="utf8")
    result = tool_handlers["discover_skills"]({})
    assert "Found 1 skill" in result["output"]
    assert "SKILL.md" in result["output"]


def test_discover_skills_recursive(tool_handlers, sandbox: Path):
    reset_registry()
    subdir = sandbox / "tools" / "mytool"
    subdir.mkdir(parents=True)
    (subdir / "SKILL.md").write_text("# Nested Skill", encoding="utf8")
    (sandbox / "SKILL.md").write_text("# Root Skill", encoding="utf8")
    result = tool_handlers["discover_skills"]({})
    assert "Found 2 skill" in result["output"]


def test_discover_skills_none_found(tool_handlers, sandbox: Path):
    reset_registry()
    result = tool_handlers["discover_skills"]({})
    assert "No SKILL.md files found" in result["output"]


def test_discover_skills_with_frontmatter(tool_handlers, sandbox: Path):
    reset_registry()
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
    reset_registry()
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
    reset_registry()
    skill_content = """---
name: algorithmic-art
description: Creating algorithmic art using p5.js with seeded randomness.
license: MIT
triggers:
  - generative art
  - p5js
chain:
  - follow-up-skill
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
    assert "Triggers:" in result["output"]
    assert "Chain:" in result["output"]
    assert "Overview" in result["output"]


def test_load_skill_direct_path(tool_handlers, sandbox: Path):
    reset_registry()
    (sandbox / "custom.md").write_text("# Custom\n\nCustom skill.", encoding="utf8")
    result = tool_handlers["load_skill"]({"path": "custom.md"})
    assert "Custom" in result["output"]


def test_load_skill_not_found(tool_handlers, sandbox: Path):
    reset_registry()
    result = tool_handlers["load_skill"]({"path": "."})
    assert "No SKILL.md found" in result["output"]


def test_suggest_skills(tool_handlers, sandbox: Path):
    reset_registry()
    skill_content = """---
name: art-generator
description: Create beautiful generative art
triggers:
  - art
  - generative
  - creative
---
"""
    (sandbox / "SKILL.md").write_text(skill_content, encoding="utf8")
    result = tool_handlers["suggest_skills"]({"query": "create generative art"})
    assert "art-generator" in result["output"]
    assert "relevance:" in result["output"]


def test_suggest_skills_no_match(tool_handlers, sandbox: Path):
    reset_registry()
    skill_content = """---
name: database-skill
description: Manage databases
triggers:
  - sql
  - postgres
---
"""
    (sandbox / "SKILL.md").write_text(skill_content, encoding="utf8")
    tool_handlers["suggest_skills"]({"query": "xyz totally unrelated"})
    # May or may not match depending on description overlap


def test_suggest_skills_empty_workspace(tool_handlers, sandbox: Path):
    reset_registry()
    result = tool_handlers["suggest_skills"]({"query": "anything"})
    assert "No skills discovered" in result["output"]


def test_parse_frontmatter():
    from steward.tools.load_skill import parse_frontmatter

    content = """---
name: test-skill
description: A test description
license: MIT
triggers:
  - keyword1
  - keyword2
---

# Body Content
"""
    frontmatter, body = parse_frontmatter(content)
    assert frontmatter["name"] == "test-skill"
    assert frontmatter["description"] == "A test description"
    assert frontmatter["license"] == "MIT"
    assert frontmatter["triggers"] == ["keyword1", "keyword2"]
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
requires:
  - other-skill
chain:
  - next-skill
---

# My Skill Title

Body paragraph.
"""
    skill = parse_skill(content, "test/SKILL.md")
    assert skill.name == "my-skill"
    assert skill.description == "Skill description from frontmatter"
    assert skill.requires == ["other-skill"]
    assert skill.chain == ["next-skill"]
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
