"""Tests for conversation history management."""
from __future__ import annotations

from steward.conversation import (
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
    # Recent messages should be preserved
    if len(truncated) > 1:
        assert truncated[-1]["content"] == "Recent response"


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
