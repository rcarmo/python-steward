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


def test_load_skill_direct_path(tool_handlers, sandbox: Path):
    (sandbox / "custom.md").write_text("# Custom\n\nCustom skill.", encoding="utf8")
    result = tool_handlers["load_skill"]({"path": "custom.md"})
    assert "Custom" in result["output"]


def test_load_skill_not_found(tool_handlers, sandbox: Path):
    result = tool_handlers["load_skill"]({"path": "."})
    assert "No SKILL.md found" in result["output"]
