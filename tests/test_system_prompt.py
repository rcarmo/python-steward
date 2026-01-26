"""Tests for system_prompt module."""
import os

from steward.system_prompt import (
    VERSION,
    build_system_prompt,
    default_system_prompt,
    get_environment_context,
)


def test_build_system_prompt_contains_tools():
    """Test that system prompt includes tool names."""
    prompt = build_system_prompt(["view", "edit", "bash"])
    assert "view" in prompt
    assert "edit" in prompt
    assert "bash" in prompt


def test_build_system_prompt_contains_version():
    """Test that system prompt includes version."""
    prompt = build_system_prompt(["view"])
    assert VERSION in prompt


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


def test_build_system_prompt_parallel_tool_calling():
    """Test that parallel tool calling guidance is present."""
    prompt = build_system_prompt(["view", "grep"])
    assert "PARALLEL TOOL CALLING" in prompt
    assert "SINGLE response" in prompt


def test_build_system_prompt_tool_guidance():
    """Test that tool-specific guidance is present."""
    prompt = build_system_prompt(["bash", "edit", "grep"])

    # bash guidance
    assert "mode=\"sync\"" in prompt or 'mode="sync"' in prompt
    assert "mode=\"async\"" in prompt or 'mode="async"' in prompt
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
    assert os.getcwd() in context


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
