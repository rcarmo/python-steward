"""Tests for llm module."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest


@pytest.fixture()
def echo_client():
    from steward.llm import build_client

    return build_client("echo", "test")


@pytest.mark.parametrize(
    "provider,model,expect_echo",
    [
        ("echo", "test-model", True),
        ("unknown_provider", "model", True),
    ],
)
def test_build_client_fallbacks(provider, model, expect_echo):
    from steward.llm import build_client

    client = build_client(provider, model)
    result = asyncio.run(client.generate([{"role": "user", "content": "test"}]))
    assert ("Echo" in result.get("content", "")) is expect_echo


@patch.dict(os.environ, {"STEWARD_OPENAI_API_KEY": "test-key"})
def test_build_client_openai():
    from steward.llm import build_client

    client = build_client("openai", "gpt-4")
    assert client is not None


@patch.dict(
    os.environ,
    {
        "STEWARD_AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
        "STEWARD_AZURE_OPENAI_KEY": "test-key",
        "STEWARD_AZURE_OPENAI_DEPLOYMENT": "test-deployment",
    },
)
def test_build_client_azure():
    from steward.llm import build_client

    client = build_client("azure", "gpt-4")
    assert client is not None


def test_echo_client_with_tools(echo_client):
    tools = [{"name": "test_tool", "description": "Test", "parameters": {"type": "object", "properties": {}}}]
    result = asyncio.run(echo_client.generate([{"role": "user", "content": "test"}], tools))
    assert "content" in result or "toolCalls" in result


def test_echo_client_multiple_messages(echo_client):
    messages = [
        {"role": "system", "content": "You are a test"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "Final message"},
    ]
    result = asyncio.run(echo_client.generate(messages))
    assert "Echo" in result.get("content", "")
    assert "Final message" in result.get("content", "")


def test_echo_client_stream_handler_called(echo_client):
    received = []

    def handler(chunk: str, done: bool) -> None:
        received.append((chunk, done))

    result = asyncio.run(echo_client.generate([{"role": "user", "content": "hi"}], stream_handler=handler))
    assert result.get("content") == "Echo: hi"
    assert received == [("Echo: hi", True)]


def test_to_openai_messages():
    from steward.llm import _to_openai_messages

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User message"},
        {
            "role": "assistant",
            "content": "Response",
            "tool_calls": [{"id": "1", "name": "test", "arguments": {"a": 1}}],
        },
        {"role": "tool", "content": "Tool result", "tool_call_id": "1"},
    ]

    result = _to_openai_messages(messages)
    assert len(result) == 4
    assert result[0]["role"] == "system"
    assert result[2]["role"] == "assistant"
    assert "tool_calls" in result[2]


def test_to_openai_tool():
    from steward.llm import _to_openai_tool

    tool = {
        "name": "test_tool",
        "description": "A test tool",
        "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}},
    }

    result = _to_openai_tool(tool)
    assert result["type"] == "function"
    assert result["function"]["name"] == "test_tool"


def test_to_tool_calls_empty():
    from steward.llm import _to_tool_calls

    assert _to_tool_calls(None) is None
    assert _to_tool_calls([]) is None


@pytest.mark.parametrize(
    "usage_details,expected_cached",
    [
        (None, None),
        (type("D", (), {"cached_tokens": 800})(), 800),
    ],
)
def test_extract_usage(usage_details, expected_cached):
    from steward.llm import _extract_usage

    completion = type(
        "C",
        (),
        {
            "usage": type(
                "U",
                (),
                {
                    "prompt_tokens": 1000,
                    "completion_tokens": 50,
                    "total_tokens": 1050,
                    "prompt_tokens_details": usage_details,
                },
            )()
        },
    )()

    result = _extract_usage(completion)
    assert result["prompt_tokens"] == 1000
    if expected_cached is None:
        assert "cached_tokens" not in result
    else:
        assert result["cached_tokens"] == expected_cached


@patch("steward.llm.AsyncOpenAI")
def test_openai_client_empty_choices(mock_openai):
    from steward.llm import OpenAIClient

    async def mock_create(**_kwargs):
        return type("Resp", (), {"choices": []})()

    mock_client = mock_openai.return_value
    mock_client.chat.completions.create = mock_create
    client = OpenAIClient("gpt-4", api_key="test", use_responses_api=False)
    result = asyncio.run(client.generate([{"role": "user", "content": "hi"}]))
    assert result["content"] is None
    assert result["toolCalls"] is None


@patch.dict(os.environ, {"STEWARD_OPENAI_API_KEY": "test-key", "STEWARD_USE_RESPONSES_API": "1"})
@patch("steward.llm.AsyncOpenAI")
def test_openai_client_responses_api_with_previous_id(mock_openai):
    from steward.llm import OpenAIClient

    response = type(
        "Resp",
        (),
        {
            "output_text": "ok",
            "id": "resp_123",
            "output": [],
            "usage": None,
        },
    )()

    async def mock_create(**_kwargs):
        return response

    mock_client = mock_openai.return_value
    mock_client.responses.create = mock_create
    client = OpenAIClient("gpt-4", api_key="test", use_responses_api=True)

    result = asyncio.run(
        client.generate(
            [{"role": "system", "content": "System"}, {"role": "user", "content": "hi"}],
            previous_response_id="resp_prev",
        )
    )
    assert result["content"] == "ok"
    assert result.get("response_id") == "resp_123"


@patch.dict(os.environ, {"STEWARD_OPENAI_API_KEY": "test-key", "STEWARD_USE_RESPONSES_API": "auto"})
@patch("steward.llm.AsyncOpenAI")
def test_openai_client_auto_selects_responses(mock_openai):
    from steward.llm import OpenAIClient

    response = type(
        "Resp",
        (),
        {
            "output_text": "ok",
            "id": "resp_auto",
            "output": [],
            "usage": None,
        },
    )()

    async def mock_create(**_kwargs):
        return response

    mock_client = mock_openai.return_value
    mock_client.responses.create = mock_create
    client = OpenAIClient("gpt-4", api_key="test", use_responses_api=None)

    result = asyncio.run(client.generate([{"role": "user", "content": "hi"}]))
    assert result.get("response_id") == "resp_auto"


def test_to_responses_tool():
    from steward.llm import _to_responses_tool

    tool = {
        "name": "test_tool",
        "description": "A test tool",
        "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}},
    }

    result = _to_responses_tool(tool)
    assert result["type"] == "function"
    assert result["name"] == "test_tool"
    assert result["description"] == "A test tool"


@pytest.mark.parametrize(
    "output,expected_count",
    [
        (None, 0),
        ([], 0),
        ([type("Item", (), {"type": "other"})()], 0),
        (
            [
                type(
                    "Item",
                    (),
                    {
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "view",
                        "arguments": '{"path": "test.py"}',
                    },
                )()
            ],
            1,
        ),
    ],
)
def test_extract_responses_tool_calls(output, expected_count):
    from steward.llm import _extract_responses_tool_calls

    response = type("R", (), {"output": output})()
    result = _extract_responses_tool_calls(response)
    count = len(result or [])
    assert count == expected_count
    if expected_count:
        assert result[0]["name"] == "view"
        assert result[0]["arguments"]["path"] == "test.py"


def test_echo_client_returns_response_id(echo_client):
    result = asyncio.run(echo_client.generate([{"role": "user", "content": "test"}]))
    assert result.get("response_id") == "echo-123"


@patch("steward.llm.AsyncOpenAI")
def test_openai_stream_tool_calls_none_keeps_previous(mock_openai):
    from steward.llm import OpenAIClient

    class Delta:
        def __init__(self, content=None, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

    class Choice:
        def __init__(self, delta):
            self.delta = delta

    class Event:
        def __init__(self, delta):
            self.choices = [Choice(delta)]

    stream_events = [
        Event(
            Delta(
                tool_calls=[
                    type(
                        "Call",
                        (),
                        {"index": 0, "id": "1", "function": type("Fn", (), {"name": "view", "arguments": "{}"})()},
                    )()
                ]
            )
        ),
        Event(Delta(content="ok", tool_calls=None)),
    ]

    async def stream_create(**_kwargs):
        for event in stream_events:
            yield event

    mock_client = mock_openai.return_value
    mock_client.chat.completions.create = stream_create
    client = OpenAIClient("gpt-4", api_key="test")
    result = asyncio.run(client.generate([{"role": "user", "content": "hi"}], stream_handler=lambda *_args: None))
    assert result["toolCalls"] is not None
