"""Tests for llm module."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import patch


def test_build_client_echo():
    from steward.llm import build_client

    client = build_client("echo", "test-model")
    result = asyncio.run(client.generate([{"role": "user", "content": "test"}]))
    assert "content" in result


def test_build_client_unknown_provider():
    from steward.llm import build_client

    # Unknown provider falls back to EchoClient
    client = build_client("unknown_provider", "model")
    result = asyncio.run(client.generate([{"role": "user", "content": "test"}]))
    assert "Echo" in result.get("content", "")


@patch.dict(os.environ, {"STEWARD_OPENAI_API_KEY": "test-key"})
def test_build_client_openai():
    from steward.llm import build_client

    client = build_client("openai", "gpt-4")
    assert client is not None


@patch.dict(os.environ, {
    "STEWARD_AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
    "STEWARD_AZURE_OPENAI_KEY": "test-key",
    "STEWARD_AZURE_OPENAI_DEPLOYMENT": "test-deployment"
})
def test_build_client_azure():
    from steward.llm import build_client

    client = build_client("azure", "gpt-4")
    assert client is not None


def test_echo_client_with_tools():
    from steward.llm import build_client

    client = build_client("echo", "test")
    tools = [{"name": "test_tool", "description": "Test", "parameters": {"type": "object", "properties": {}}}]
    result = asyncio.run(client.generate([{"role": "user", "content": "test"}], tools))
    assert "content" in result or "toolCalls" in result


def test_echo_client_multiple_messages():
    from steward.llm import build_client

    client = build_client("echo", "test")
    messages = [
        {"role": "system", "content": "You are a test"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "Final message"},
    ]
    result = asyncio.run(client.generate(messages))
    assert "Echo" in result.get("content", "")
    assert "Final message" in result.get("content", "")


def test_echo_client_stream_handler_called():
    from steward.llm import build_client

    received = []

    def handler(chunk: str, done: bool) -> None:
        received.append((chunk, done))

    client = build_client("echo", "test")
    result = asyncio.run(client.generate([{"role": "user", "content": "hi"}], stream_handler=handler))
    assert result.get("content") == "Echo: hi"
    assert received == [("Echo: hi", True)]


def test_to_openai_messages():
    from steward.llm import _to_openai_messages

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User message"},
        {"role": "assistant", "content": "Response", "tool_calls": [
            {"id": "1", "name": "test", "arguments": {"a": 1}}
        ]},
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
        "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}}
    }

    result = _to_openai_tool(tool)
    assert result["type"] == "function"
    assert result["function"]["name"] == "test_tool"


def test_to_tool_calls_empty():
    from steward.llm import _to_tool_calls

    assert _to_tool_calls(None) is None
    assert _to_tool_calls([]) is None


def test_extract_usage_none():
    from steward.llm import _extract_usage

    assert _extract_usage(None) is None
    assert _extract_usage(type("C", (), {"usage": None})()) is None


def test_extract_usage_basic():
    from steward.llm import _extract_usage

    completion = type("C", (), {
        "usage": type("U", (), {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": None
        })()
    })()

    result = _extract_usage(completion)
    assert result["prompt_tokens"] == 100
    assert result["completion_tokens"] == 50
    assert result["total_tokens"] == 150
    assert "cached_tokens" not in result


def test_extract_usage_with_cache():
    from steward.llm import _extract_usage

    completion = type("C", (), {
        "usage": type("U", (), {
            "prompt_tokens": 1000,
            "completion_tokens": 50,
            "total_tokens": 1050,
            "prompt_tokens_details": type("D", (), {"cached_tokens": 800})()
        })()
    })()

    result = _extract_usage(completion)
    assert result["prompt_tokens"] == 1000
    assert result["cached_tokens"] == 800


@patch('steward.llm.AsyncOpenAI')
def test_openai_client_empty_choices(mock_openai):
    import asyncio

    from steward.llm import OpenAIClient

    async def mock_create(**_kwargs):
        return type("Resp", (), {"choices": []})()

    mock_client = mock_openai.return_value
    mock_client.chat.completions.create = mock_create
    client = OpenAIClient("gpt-4", api_key="test")
    result = asyncio.run(client.generate([{"role": "user", "content": "hi"}]))
    assert result["content"] is None
    assert result["toolCalls"] is None


def test_to_responses_tool():
    from steward.llm import _to_responses_tool

    tool = {
        "name": "test_tool",
        "description": "A test tool",
        "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}}
    }

    result = _to_responses_tool(tool)
    assert result["type"] == "function"
    assert result["name"] == "test_tool"
    assert result["description"] == "A test tool"


def test_extract_responses_tool_calls_none():
    from steward.llm import _extract_responses_tool_calls

    assert _extract_responses_tool_calls(None) is None
    assert _extract_responses_tool_calls(type("R", (), {"output": None})()) is None


def test_extract_responses_tool_calls():
    from steward.llm import _extract_responses_tool_calls

    # Mock a Responses API response with function calls
    output = [
        type("Item", (), {
            "type": "function_call",
            "call_id": "call_123",
            "name": "view",
            "arguments": '{"path": "test.py"}'
        })()
    ]
    response = type("R", (), {"output": output})()

    result = _extract_responses_tool_calls(response)
    assert result is not None
    assert len(result) == 1
    assert result[0]["name"] == "view"
    assert result[0]["arguments"]["path"] == "test.py"


def test_echo_client_returns_response_id():
    from steward.llm import build_client

    client = build_client("echo", "test-model")
    result = asyncio.run(client.generate([{"role": "user", "content": "test"}]))
    assert result.get("response_id") == "echo-123"


@patch('steward.llm.AsyncOpenAI')
def test_openai_stream_tool_calls_none_keeps_previous(mock_openai):
    import asyncio

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
        Event(Delta(tool_calls=[
            type("Call", (), {"index": 0, "id": "1", "function": type("Fn", (), {"name": "view", "arguments": "{}"})()})()
        ])),
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
