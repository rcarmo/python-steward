"""Tests for conversation history management."""
from __future__ import annotations

from steward.conversation import (
    compact_history,
    count_tokens,
    get_conversation_stats,
    should_truncate,
    truncate_history,
)


def test_count_tokens_simple():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]
    tokens = count_tokens(messages)
    assert tokens > 0
    assert tokens < 100  # Should be small for this


def test_count_tokens_with_tool_calls():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "List files"},
        {
            "role": "assistant",
            "content": "I'll list the files.",
            "tool_calls": [
                {"id": "call_1", "name": "view", "arguments": {"path": "."}}
            ]
        },
        {"role": "tool", "content": "file1.txt\nfile2.txt", "tool_call_id": "call_1"},
    ]
    tokens = count_tokens(messages)
    assert tokens > 20


def test_truncate_history_preserves_tool_pairs():
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Message 1"},
        {
            "role": "assistant",
            "content": "Using tool",
            "tool_calls": [{"id": "call_1", "name": "view", "arguments": {"path": "."}}],
        },
        {"role": "tool", "content": "file1.txt", "tool_call_id": "call_1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
    ]

    truncated, _ = truncate_history(messages, max_tokens=120)
    # If assistant tool_call kept, tool response must be kept too
    roles = [m["role"] for m in truncated]
    if "assistant" in roles and any(m.get("tool_calls") for m in truncated):
        assert "tool" in roles


def test_truncate_history_keeps_system():
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
    ]

    # Very low limit to force truncation
    truncated, dropped = truncate_history(messages, max_tokens=100)

    # System prompt should always be kept
    assert truncated[0]["role"] == "system"
    assert truncated[0]["content"] == "System prompt"


def test_truncate_history_overbudget_system_keeps_user():
    messages = [
        {"role": "system", "content": "System prompt " * 1000},
        {"role": "user", "content": "User message"},
    ]
    truncated, _ = truncate_history(messages, max_tokens=100)
    roles = [m["role"] for m in truncated]
    assert "system" in roles
    assert "user" in roles


def test_truncate_history_keeps_recent():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Old message"},
        {"role": "assistant", "content": "Old response"},
        {"role": "user", "content": "Recent message"},
        {"role": "assistant", "content": "Recent response"},
    ]

    # Low limit but enough for system + recent
    truncated, dropped = truncate_history(messages, max_tokens=200)

    # Should keep system and most recent messages
    assert truncated[0]["role"] == "system"
    # Recent user message should be preserved
    if len(truncated) > 1:
        assert "Recent" in truncated[-1]["content"]


def test_truncate_history_no_change_under_limit():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hello"},
    ]

    # High limit - no truncation needed
    truncated, dropped = truncate_history(messages, max_tokens=100000)

    assert len(truncated) == len(messages)
    assert dropped == 0


def test_should_truncate():
    # Small conversation - should not truncate
    small = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hello"},
    ]
    assert not should_truncate(small, max_tokens=100000)


def test_get_conversation_stats():
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
        {"role": "tool", "content": "Tool output", "tool_call_id": "123"},
    ]

    stats = get_conversation_stats(messages)

    assert stats["message_count"] == 6
    assert stats["user_messages"] == 2
    assert stats["assistant_messages"] == 2
    assert stats["tool_messages"] == 1
    assert stats["total_tokens"] > 0


def test_truncate_empty_messages():
    messages = []
    truncated, dropped = truncate_history(messages, max_tokens=1000)
    assert truncated == []
    assert dropped == 0


def test_truncate_no_system_prompt():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    truncated, dropped = truncate_history(messages, max_tokens=100000)
    assert len(truncated) == 2
    assert truncated[0]["role"] == "user"


def test_compact_history_summarizes_old_tools():
    """Test that compact_history summarizes old tool calls."""
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Task 1"},
        {
            "role": "assistant",
            "content": "Reading file",
            "tool_calls": [{"id": "c1", "name": "view", "arguments": {"path": "file1.py"}}],
        },
        {"role": "tool", "content": "def foo(): pass", "tool_call_id": "c1"},
        {"role": "user", "content": "Task 2"},
        {
            "role": "assistant",
            "content": "Editing",
            "tool_calls": [{"id": "c2", "name": "edit", "arguments": {"path": "file1.py"}}],
        },
        {"role": "tool", "content": "Edited", "tool_call_id": "c2"},
        {"role": "user", "content": "Task 3"},
        {"role": "assistant", "content": "Done"},
        {"role": "user", "content": "Task 4"},
        {"role": "assistant", "content": "Done again"},
    ]

    compacted, summary = compact_history(messages, keep_recent_turns=2)

    # Should have compacted old turns
    assert len(compacted) < len(messages)
    # Summary should mention file operations
    assert "Prior context" in summary or summary == ""


def test_compact_history_with_bash_and_search():
    """Test that compact_history summarizes bash and grep commands."""
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Search"},
        {
            "role": "assistant",
            "content": "Searching",
            "tool_calls": [
                {"id": "c1", "name": "grep", "arguments": {"pattern": "TODO"}},
                {"id": "c2", "name": "bash", "arguments": {"command": "make test"}},
            ],
        },
        {"role": "tool", "content": "file.py:1:TODO", "tool_call_id": "c1"},
        {"role": "tool", "content": "ok", "tool_call_id": "c2"},
        {"role": "user", "content": "Next task"},
        {"role": "assistant", "content": "Done"},
        {"role": "user", "content": "Another task"},
        {"role": "assistant", "content": "Done"},
        {"role": "user", "content": "Final task"},
        {"role": "assistant", "content": "Done"},
    ]

    compacted, summary = compact_history(messages, keep_recent_turns=2)

    # Should summarize searches and commands
    assert len(compacted) < len(messages)


def test_compact_history_no_change_when_short():
    """Test that compact_history doesn't change short conversations."""
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    compacted, summary = compact_history(messages, keep_recent_turns=5)

    assert len(compacted) == len(messages)
    assert summary == ""


def test_compact_history_empty():
    """Test compact_history with empty messages."""
    compacted, summary = compact_history([], keep_recent_turns=5)
    assert compacted == []
    assert summary == ""
