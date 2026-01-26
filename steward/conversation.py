"""Conversation history management with token-aware sliding window."""
from __future__ import annotations

import json
from typing import List, Tuple

import tiktoken

from .types import Message

# Default token limits (conservative for safety margin)
DEFAULT_MAX_HISTORY_TOKENS = 100_000
RESPONSE_RESERVE_TOKENS = 4_000  # Reserve for model response


def count_message_tokens(message: Message, encoding: tiktoken.Encoding) -> int:
    """Count tokens in a single message."""
    tokens = 0

    # Role token overhead (approx 4 tokens per message for role/formatting)
    tokens += 4

    # Content
    content = message.get("content") or ""
    if content:
        tokens += len(encoding.encode(content))

    # Tool calls (if present)
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for call in tool_calls:
            # Function name and id
            tokens += len(encoding.encode(call.get("name", "")))
            tokens += len(encoding.encode(call.get("id", "")))
            # Arguments as JSON
            args = call.get("arguments", {})
            if isinstance(args, dict):
                tokens += len(encoding.encode(json.dumps(args)))

    # Tool call ID for tool responses
    if message.get("tool_call_id"):
        tokens += len(encoding.encode(message["tool_call_id"]))

    return tokens


def count_tokens(messages: List[Message], model: str = "gpt-4") -> int:
    """Count total tokens in a message list."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models
        encoding = tiktoken.get_encoding("cl100k_base")

    total = 0
    for msg in messages:
        total += count_message_tokens(msg, encoding)

    # Add overhead for conversation structure
    total += 3  # Every reply is primed with assistant

    return total


def truncate_history(
    messages: List[Message],
    max_tokens: int = DEFAULT_MAX_HISTORY_TOKENS,
    model: str = "gpt-4",
) -> Tuple[List[Message], int]:
    """
    Truncate conversation history to fit within token budget.

    Keeps:
    - System prompt (always first)
    - Most recent messages that fit within budget

    Returns:
        Tuple of (truncated messages, tokens dropped)
    """
    if not messages:
        return messages, 0

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    # Reserve tokens for response
    budget = max_tokens - RESPONSE_RESERVE_TOKENS

    # Always keep system prompt if present
    system_msg = None
    other_messages = messages
    if messages and messages[0].get("role") == "system":
        system_msg = messages[0]
        other_messages = messages[1:]

    # Calculate system prompt tokens
    system_tokens = count_message_tokens(system_msg, encoding) if system_msg else 0

    if system_tokens >= budget:
        # System prompt alone exceeds budget - truncate it
        return [system_msg] if system_msg else [], count_tokens(messages, model)

    remaining_budget = budget - system_tokens

    # Build from the end (most recent) to fit within budget
    kept_messages: List[Message] = []
    kept_tokens = 0

    for msg in reversed(other_messages):
        msg_tokens = count_message_tokens(msg, encoding)
        if kept_tokens + msg_tokens <= remaining_budget:
            kept_messages.insert(0, msg)
            kept_tokens += msg_tokens
        else:
            # Can't fit this message, stop
            break

    # Calculate how many tokens we dropped
    original_tokens = count_tokens(messages, model)

    # Reconstruct with system prompt
    result = []
    if system_msg:
        result.append(system_msg)
    result.extend(kept_messages)

    final_tokens = count_tokens(result, model)
    dropped_tokens = original_tokens - final_tokens

    return result, dropped_tokens


def should_truncate(
    messages: List[Message],
    max_tokens: int = DEFAULT_MAX_HISTORY_TOKENS,
    model: str = "gpt-4",
) -> bool:
    """Check if conversation needs truncation."""
    current_tokens = count_tokens(messages, model)
    return current_tokens > (max_tokens - RESPONSE_RESERVE_TOKENS)


def get_conversation_stats(messages: List[Message], model: str = "gpt-4") -> dict:
    """Get statistics about the conversation."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    total_tokens = 0
    message_count = len(messages)
    user_messages = 0
    assistant_messages = 0
    tool_messages = 0

    for msg in messages:
        total_tokens += count_message_tokens(msg, encoding)
        role = msg.get("role")
        if role == "user":
            user_messages += 1
        elif role == "assistant":
            assistant_messages += 1
        elif role == "tool":
            tool_messages += 1

    return {
        "total_tokens": total_tokens,
        "message_count": message_count,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "tool_messages": tool_messages,
    }
