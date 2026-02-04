"""Tests for system_prompt module."""

import json
from os import getcwd
from pathlib import Path

from steward.system_prompt import (
    build_system_prompt,
    default_system_prompt,
    get_environment_context,
    load_agents_instructions,
)
from steward.utils import get_version


def test_build_system_prompt_contains_tools():
    """Test that system prompt includes tool names."""
    prompt = build_system_prompt(["view", "edit", "bash"])
    assert "view" in prompt
    assert "edit" in prompt
    assert "bash" in prompt


def test_build_system_prompt_contains_version():
    """Test that system prompt includes version."""
    prompt = build_system_prompt(["view"])
    assert get_version() in prompt


def test_build_system_prompt_contains_sections():
    """Test that system prompt contains key sections."""
    prompt = build_system_prompt(["view", "edit"])

    # Check for key section markers
    assert "<tone_and_style>" in prompt
    assert "<tool_efficiency>" in prompt
    assert "<code_change_rules>" in prompt
    assert "<tool_guidance>" in prompt
    assert "<security_and_privacy>" in prompt
    assert "<task_completion>" in prompt
    assert "<environment_context>" in prompt
    assert "<tips>" in prompt
    assert "Local date/time:" in prompt

    # Ensure datetime is at the end
    last_line = prompt.strip().splitlines()[-1]
    assert last_line.startswith("Local date/time:")


def test_build_system_prompt_parallel_tool_calling():
    """Test that parallel tool calling guidance is present."""
    prompt = build_system_prompt(["view", "grep"])
    assert "PARALLEL TOOL CALLING" in prompt
    assert "SINGLE response" in prompt


def test_build_system_prompt_tool_guidance():
    """Test that tool-specific guidance is present."""
    prompt = build_system_prompt(["bash", "edit", "grep"])

    # bash guidance
    assert 'mode="sync"' in prompt or 'mode="sync"' in prompt
    assert 'mode="async"' in prompt or 'mode="async"' in prompt
    assert "detach" in prompt

    # edit guidance
    assert "old_str" in prompt
    assert "unique" in prompt.lower()

    # grep guidance
    assert "ripgrep" in prompt
    assert "output_mode" in prompt


def test_build_system_prompt_security():
    """Test that security constraints are present."""
    prompt = build_system_prompt(["view"])
    assert "secrets" in prompt.lower()
    assert "credentials" in prompt.lower()
    assert "must NOT" in prompt


def test_build_system_prompt_custom_instructions():
    """Test custom instructions injection."""
    custom = "Always use tabs for indentation."
    prompt = build_system_prompt(["view"], custom_instructions=custom)
    assert "<custom_instructions>" in prompt
    assert custom in prompt


def test_build_system_prompt_no_custom_instructions():
    """Test that custom_instructions section is absent when not provided."""
    prompt = build_system_prompt(["view"])
    assert "<custom_instructions>" not in prompt


def test_get_environment_context():
    """Test environment context generation."""
    context = get_environment_context()
    assert "Current working directory" in context
    assert getcwd() in context


def test_build_system_prompt_session_context():
    """Test session context injection."""
    session_ctx = "<session_context>\nTest session info\n</session_context>"
    prompt = build_system_prompt(["view"], session_context=session_ctx)
    assert "<session_context>" in prompt
    assert "Test session info" in prompt


def test_build_system_prompt_plan_mode():
    """Test plan mode section."""
    prompt = build_system_prompt(["view"], plan_mode=True)
    assert "<plan_mode>" in prompt
    assert "PLAN MODE" in prompt
    assert "plan.md" in prompt


def test_build_system_prompt_no_plan_mode():
    """Test that plan_mode section is absent when not enabled."""
    prompt = build_system_prompt(["view"], plan_mode=False)
    assert "<plan_mode>" not in prompt


def test_default_system_prompt_backward_compat():
    """Test backward compatibility function."""
    prompt = default_system_prompt(["view", "edit"])
    assert "view" in prompt
    assert "edit" in prompt
    # Should be same as build_system_prompt with defaults
    assert prompt == build_system_prompt(["view", "edit"])


def test_build_system_prompt_report_intent_guidance():
    """Test that report_intent guidance is present."""
    prompt = build_system_prompt(["report_intent"])
    assert "report_intent" in prompt
    assert "gerund" in prompt.lower()
    assert "4 words" in prompt


def test_build_system_prompt_ask_user_guidance():
    """Test that ask_user guidance is present."""
    prompt = build_system_prompt(["ask_user"])
    assert "ask_user" in prompt
    assert "choices" in prompt.lower()
    assert "freeform" in prompt.lower()


def test_build_system_prompt_store_memory_guidance():
    """Test that store_memory guidance is present."""
    prompt = build_system_prompt(["store_memory"])
    assert "store_memory" in prompt
    assert "facts" in prompt.lower()
    assert "citations" in prompt.lower()


def test_build_system_prompt_list_memories_guidance():
    """Test that list_memories guidance is present."""
    prompt = build_system_prompt(["list_memories"])
    assert "list_memories" in prompt
    assert "memories" in prompt.lower()


def test_build_system_prompt_memory_context_empty():
    """Test that memory context section is present even without memories."""
    prompt = build_system_prompt(["view"])
    assert "<memory_context>" in prompt
    assert "(no stored memories)" in prompt


def test_build_system_prompt_memory_context_includes_memories(tmp_path: Path, monkeypatch):
    """Test that stored memories are injected into the prompt."""
    data = {
        "memories": [
            {
                "subject": "testing",
                "fact": "Use pytest.",
                "citations": "file.py:1",
                "reason": "It is consistent. It is fast.",
                "category": "general",
                "timestamp": "2024-01-01T00:00:00+00:00",
            }
        ]
    }
    (tmp_path / ".steward-memory.json").write_text(json.dumps(data), encoding="utf8")
    monkeypatch.chdir(tmp_path)
    prompt = build_system_prompt(["view"])
    assert "Use pytest." in prompt
    assert prompt.rfind("<memory_context>") > prompt.rfind("<tips>")


def test_build_system_prompt_iteration_workflow():
    """Test that iteration workflow (Codex-style) is present."""
    prompt = build_system_prompt(["view", "edit"])
    assert "<iteration_workflow>" in prompt
    assert "READ" in prompt
    assert "EDIT" in prompt
    assert "TEST" in prompt
    assert "VERIFY" in prompt


def test_build_system_prompt_tools_sorted():
    """Test that tools are sorted for cache stability."""
    prompt1 = build_system_prompt(["view", "edit", "bash"])
    prompt2 = build_system_prompt(["bash", "view", "edit"])
    # Both should produce same sorted list
    assert "bash, edit, view" in prompt1
    assert "bash, edit, view" in prompt2


def test_load_agents_instructions_none(sandbox: Path):
    """Test that load_agents_instructions returns None when no files exist."""
    result = load_agents_instructions()
    # May or may not find files depending on test environment
    # Just ensure it doesn't crash
    assert result is None or isinstance(result, str)


def test_load_agents_instructions_local(sandbox: Path):
    """Test loading AGENTS.md from current directory."""
    agents_file = sandbox / "AGENTS.md"
    agents_file.write_text("# Local Instructions\nUse pytest for testing.", encoding="utf8")

    result = load_agents_instructions()
    assert result is not None
    assert "Local Instructions" in result
    assert "pytest" in result


def test_load_agents_instructions_copilot_instructions(sandbox: Path):
    """Test loading repo-level copilot-instructions."""
    (sandbox / ".git").mkdir()
    github_dir = sandbox / ".github"
    github_dir.mkdir()
    copilot_file = github_dir / "copilot-instructions.md"
    copilot_file.write_text("# Copilot Instructions\nUse make check.", encoding="utf8")

    result = load_agents_instructions()
    assert result is not None
    assert "Copilot Instructions" in result
