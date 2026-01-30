"""Tests for runner module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_default_system_prompt():
    from steward.system_prompt import default_system_prompt

    prompt = default_system_prompt(["view", "grep", "create"])
    assert "view" in prompt
    assert "grep" in prompt
    assert "create" in prompt
    assert "Steward" in prompt


def test_format_tool_calls():
    from steward.runner import format_tool_calls

    calls = [
        {"id": "1", "name": "view", "arguments": {}},
        {"id": "2", "name": "grep", "arguments": {}},
    ]
    result = format_tool_calls(calls)
    assert "view" in result
    assert "grep" in result


def test_summarize_plan_args():
    from steward.runner import summarize_plan_args

    # Non-todo call returns None
    call = {"id": "1", "name": "view", "arguments": {"path": "test.txt"}}
    assert summarize_plan_args(call) is None

    # Todo call returns summary
    call = {
        "id": "1",
        "name": "manage_todo_list",
        "arguments": {
            "todoList": [
                {"id": 1, "title": "Task 1", "status": "pending"},
                {"id": 2, "title": "Task 2", "status": "done"},
            ]
        },
    }
    result = summarize_plan_args(call)
    assert "size=2" in result
    assert "1,2" in result


def test_synthesize_meta_tool():
    import asyncio

    from steward.logger import Logger
    from steward.runner import synthesize_meta_tool_async

    async def mock_generate(*args, **kwargs):
        return {"content": "Synthesized response"}

    mock_client = MagicMock()
    mock_client.generate = mock_generate

    mock_logger = MagicMock(spec=Logger)
    mock_logger.start_spinner.return_value = MagicMock()

    result = {"meta_prompt": "Synthesize this: test data", "meta_context": "test data"}

    output = asyncio.run(synthesize_meta_tool_async(mock_client, result, mock_logger))
    assert output == "Synthesized response"


def test_synthesize_meta_tool_error():
    import asyncio

    from steward.logger import Logger
    from steward.runner import synthesize_meta_tool_async

    async def mock_generate(*args, **kwargs):
        raise Exception("API error")

    mock_client = MagicMock()
    mock_client.generate = mock_generate

    mock_logger = MagicMock(spec=Logger)
    mock_logger.start_spinner.return_value = MagicMock()

    result = {"meta_prompt": "test prompt", "meta_context": "context data"}

    output = asyncio.run(synthesize_meta_tool_async(mock_client, result, mock_logger))
    assert "[synthesis error]" in output
    assert "context data" in output


def test_synthesize_meta_tool_empty_response():
    import asyncio

    from steward.logger import Logger
    from steward.runner import synthesize_meta_tool_async

    async def mock_generate(*args, **kwargs):
        return {"content": None}

    mock_client = MagicMock()
    mock_client.generate = mock_generate

    mock_logger = MagicMock(spec=Logger)
    mock_logger.start_spinner.return_value = MagicMock()

    result = {"meta_prompt": "test", "meta_context": "ctx"}
    output = asyncio.run(synthesize_meta_tool_async(mock_client, result, mock_logger))
    assert "no synthesis" in output.lower()


def test_runner_result_has_response_id():
    from steward.runner import RunnerResult

    result = RunnerResult(response="test", messages=[], last_response_id="resp_123")
    assert result.last_response_id == "resp_123"


def test_runner_options_has_previous_response_id():
    from steward.runner import RunnerOptions

    options = RunnerOptions(prompt="test", previous_response_id="resp_456")
    assert options.previous_response_id == "resp_456"


def test_runner_options():
    from steward.llm import EchoClient
    from steward.runner import RunnerOptions

    opts = RunnerOptions(
        prompt="test prompt",
        system_prompt="custom system",
        max_steps=10,
        provider="echo",
        model="test-model",
        llm_client=EchoClient("test-model"),
    )
    assert opts.prompt == "test prompt"
    assert opts.max_steps == 10
    assert opts.llm_client is not None


@patch("steward.runner.build_client")
@patch("steward.runner.discover_tools")
def test_run_steward_basic(mock_discover, mock_build, sandbox: Path):
    from steward.runner import RunnerOptions, run_steward

    # Setup mocks
    mock_discover.return_value = ([], {})

    async def mock_generate(*args, **kwargs):
        return {"content": "Final response"}

    mock_client = MagicMock()
    mock_client.generate = mock_generate
    mock_build.return_value = mock_client

    opts = RunnerOptions(prompt="test", provider="echo", model="test", enable_human_logs=False, enable_file_logs=False)

    result = run_steward(opts)
    assert result == "Final response"
