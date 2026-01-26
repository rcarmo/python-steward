"""Tests for skill registry."""
from __future__ import annotations

from pathlib import Path

from steward.skills import SkillRegistry, get_registry, reset_registry


def test_registry_discover(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---
# Test
""", encoding="utf8")

    registry = SkillRegistry()
    count = registry.discover(tmp_path)
    assert count == 1
    assert registry.get("test-skill") is not None


def test_registry_discover_recursive(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("---\nname: root\ndescription: Root skill\n---\n", encoding="utf8")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "SKILL.md").write_text("---\nname: nested\ndescription: Nested skill\n---\n", encoding="utf8")

    registry = SkillRegistry()
    count = registry.discover(tmp_path)
    assert count == 2


def test_registry_match_by_name(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("""---
name: algorithmic-art
description: Creating generative art
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    matches = registry.match("algorithmic art")
    assert len(matches) >= 1
    assert matches[0][0].name == "algorithmic-art"
    assert matches[0][1] > 0


def test_registry_match_by_trigger(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("""---
name: art-skill
description: Art creation
triggers:
  - generative
  - p5js
  - creative coding
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    matches = registry.match("create generative visuals")
    assert len(matches) >= 1
    assert matches[0][0].name == "art-skill"


def test_registry_match_by_description(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("""---
name: mcp-skill
description: Building MCP servers for LLM integration
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    matches = registry.match("build an MCP server")
    assert len(matches) >= 1
    assert matches[0][0].name == "mcp-skill"


def test_registry_get_chain(tmp_path: Path):
    (tmp_path / "skill1.md").write_text("""---
name: skill-a
description: First skill
chain:
  - skill-b
---
""", encoding="utf8")
    # Rename to SKILL.md in separate dirs
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "SKILL.md").write_text("""---
name: skill-a
description: First skill
chain:
  - skill-b
---
""", encoding="utf8")

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "SKILL.md").write_text("""---
name: skill-b
description: Second skill
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    chain = registry.get_chain("skill-a")
    assert len(chain) == 1
    assert chain[0].name == "skill-b"


def test_registry_get_dependencies(tmp_path: Path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "SKILL.md").write_text("""---
name: skill-a
description: First skill
---
""", encoding="utf8")

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "SKILL.md").write_text("""---
name: skill-b
description: Second skill
requires:
  - skill-a
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    deps = registry.get_dependencies("skill-b")
    assert len(deps) == 1
    assert deps[0].name == "skill-a"


def test_registry_get_dependents(tmp_path: Path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "SKILL.md").write_text("""---
name: skill-a
description: First skill
---
""", encoding="utf8")

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "SKILL.md").write_text("""---
name: skill-b
description: Second skill
requires:
  - skill-a
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    dependents = registry.get_dependents("skill-a")
    assert len(dependents) == 1
    assert dependents[0].name == "skill-b"


def test_registry_build_execution_order(tmp_path: Path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "SKILL.md").write_text("""---
name: skill-a
description: First skill
chain:
  - skill-c
---
""", encoding="utf8")

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "SKILL.md").write_text("""---
name: skill-b
description: Dependency skill
---
""", encoding="utf8")

    dir_c = tmp_path / "c"
    dir_c.mkdir()
    (dir_c / "SKILL.md").write_text("""---
name: skill-c
description: Final skill
requires:
  - skill-b
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    order = registry.build_execution_order("skill-a")
    names = [s.name for s in order]

    # skill-a first, then skill-b (dep of c), then skill-c
    assert names.index("skill-a") < names.index("skill-c")
    assert names.index("skill-b") < names.index("skill-c")


def test_global_registry():
    reset_registry()
    reg1 = get_registry()
    reg2 = get_registry()
    assert reg1 is reg2


def test_format_suggestions(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("""---
name: test-skill
description: A test skill for testing
requires:
  - other-skill
chain:
  - follow-up
---
""", encoding="utf8")

    registry = SkillRegistry()
    registry.discover(tmp_path)

    matches = registry.match("test", limit=1)
    output = registry.format_suggestions(matches)

    assert "test-skill" in output
    assert "Requires:" in output
    assert "Chains to:" in output
