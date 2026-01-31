"""Tests for runner module."""

from __future__ import annotations

import asyncio
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


def test_runner_options_has_acp_fields():
    """Test that RunnerOptions has the new ACP-related fields."""
    from steward.acp_events import AcpEventQueue, CancellationToken
    from steward.runner import RunnerOptions

    event_queue = AcpEventQueue("test-session")
    cancellation_token = CancellationToken()

    opts = RunnerOptions(
        prompt="test",
        event_queue=event_queue,
        cancellation_token=cancellation_token,
        require_permission=True,
    )
    assert opts.event_queue is event_queue
    assert opts.cancellation_token is cancellation_token
    assert opts.require_permission is True


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


def test_execute_tools_parallel_with_event_queue():
    """Test that execute_tools_parallel emits events to the queue."""
    from steward.acp_events import AcpEventQueue, AcpEventType
    from steward.logger import Logger
    from steward.runner import execute_tools_parallel

    event_queue = AcpEventQueue("test-session")
    mock_logger = MagicMock(spec=Logger)

    def mock_tool_handler(args):
        return {"id": "test", "output": "success"}

    tool_calls = [
        {"id": "call-1", "name": "test_tool", "arguments": {"arg": "value"}},
    ]
    tool_handlers = {"test_tool": mock_tool_handler}

    results = asyncio.run(
        execute_tools_parallel(
            tool_calls=tool_calls,
            tool_handlers=tool_handlers,
            client=MagicMock(),
            logger=mock_logger,
            step=0,
            event_queue=event_queue,
        )
    )

    assert len(results) == 1
    assert results[0]["output"] == "success"

    # Check that events were emitted
    events = asyncio.run(event_queue.drain())
    event_types = [e.event_type for e in events]
    assert AcpEventType.TOOL_START in event_types
    assert AcpEventType.TOOL_COMPLETE in event_types


def test_execute_tools_parallel_emits_failed_event_on_error():
    """Test that execute_tools_parallel emits TOOL_FAILED on handler error."""
    from steward.acp_events import AcpEventQueue, AcpEventType
    from steward.logger import Logger
    from steward.runner import execute_tools_parallel

    event_queue = AcpEventQueue("test-session")
    mock_logger = MagicMock(spec=Logger)

    def failing_handler(args):
        raise ValueError("Tool failed!")

    tool_calls = [
        {"id": "call-1", "name": "failing_tool", "arguments": {}},
    ]
    tool_handlers = {"failing_tool": failing_handler}

    results = asyncio.run(
        execute_tools_parallel(
            tool_calls=tool_calls,
            tool_handlers=tool_handlers,
            client=MagicMock(),
            logger=mock_logger,
            step=0,
            event_queue=event_queue,
        )
    )

    assert len(results) == 1
    assert results[0]["error"] is True
    assert "Tool failed!" in results[0]["output"]

    events = asyncio.run(event_queue.drain())
    event_types = [e.event_type for e in events]
    assert AcpEventType.TOOL_START in event_types
    assert AcpEventType.TOOL_FAILED in event_types


def test_execute_tools_parallel_respects_cancellation():
    """Test that execute_tools_parallel checks cancellation token."""
    from steward.acp_events import AcpEventQueue, CancellationToken
    from steward.logger import Logger
    from steward.runner import execute_tools_parallel

    event_queue = AcpEventQueue("test-session")
    cancellation_token = CancellationToken()
    cancellation_token.cancel()  # Pre-cancel

    mock_logger = MagicMock(spec=Logger)

    def mock_handler(args):
        return {"id": "test", "output": "should not run"}

    tool_calls = [
        {"id": "call-1", "name": "test_tool", "arguments": {}},
    ]
    tool_handlers = {"test_tool": mock_handler}

    results = asyncio.run(
        execute_tools_parallel(
            tool_calls=tool_calls,
            tool_handlers=tool_handlers,
            client=MagicMock(),
            logger=mock_logger,
            step=0,
            event_queue=event_queue,
            cancellation_token=cancellation_token,
        )
    )

    assert len(results) == 1
    assert results[0]["error"] is True
    assert "cancelled" in results[0]["output"].lower()


def test_execute_tools_parallel_unknown_tool():
    """Test that execute_tools_parallel handles unknown tools."""
    from steward.acp_events import AcpEventQueue, AcpEventType
    from steward.logger import Logger
    from steward.runner import execute_tools_parallel

    event_queue = AcpEventQueue("test-session")
    mock_logger = MagicMock(spec=Logger)

    tool_calls = [
        {"id": "call-1", "name": "nonexistent_tool", "arguments": {}},
    ]
    tool_handlers = {}  # No handlers

    results = asyncio.run(
        execute_tools_parallel(
            tool_calls=tool_calls,
            tool_handlers=tool_handlers,
            client=MagicMock(),
            logger=mock_logger,
            step=0,
            event_queue=event_queue,
        )
    )

    assert len(results) == 1
    assert results[0]["error"] is True
    assert "Unknown tool" in results[0]["output"]

    events = asyncio.run(event_queue.drain())
    event_types = [e.event_type for e in events]
    assert AcpEventType.TOOL_FAILED in event_types


def test_parse_todo_output():
    """Test parsing update_todo output into plan entries."""
    from steward.runner import _parse_todo_output

    # Test with mixed completed and pending items
    output = """TODO list updated: 2/4 completed

- [x] Setup project structure
- [x] Implement feature A
- [ ] Write tests
- [ ] Update documentation"""

    entries = _parse_todo_output(output)
    assert len(entries) == 4
    assert entries[0]["content"] == "Setup project structure"
    assert entries[0]["status"] == "completed"
    assert entries[1]["content"] == "Implement feature A"
    assert entries[1]["status"] == "completed"
    assert entries[2]["content"] == "Write tests"
    assert entries[2]["status"] == "pending"
    assert entries[3]["content"] == "Update documentation"
    assert entries[3]["status"] == "pending"


def test_parse_todo_output_empty():
    """Test parsing empty/no-checkbox output."""
    from steward.runner import _parse_todo_output

    # Test with just text, no checkboxes
    output = "TODO list updated\n\nSome header"
    entries = _parse_todo_output(output)
    assert entries == []


def test_execute_tools_parallel_emits_plan_update():
    """Test that update_todo tool emits plan update events."""
    from steward.acp_events import AcpEventQueue, AcpEventType
    from steward.logger import Logger
    from steward.runner import execute_tools_parallel

    event_queue = AcpEventQueue("test-session")
    mock_logger = MagicMock(spec=Logger)

    def update_todo_handler(args):
        return {
            "id": "update_todo",
            "output": "TODO list updated: 1/2 completed\n\n- [x] Done task\n- [ ] Pending task",
        }

    tool_calls = [
        {"id": "call-1", "name": "update_todo", "arguments": {"todos": "test"}},
    ]
    tool_handlers = {"update_todo": update_todo_handler}

    results = asyncio.run(
        execute_tools_parallel(
            tool_calls=tool_calls,
            tool_handlers=tool_handlers,
            client=MagicMock(),
            logger=mock_logger,
            step=0,
            event_queue=event_queue,
        )
    )

    assert len(results) == 1
    assert "TODO list updated" in results[0]["output"]

    events = asyncio.run(event_queue.drain())
    event_types = [e.event_type for e in events]
    assert AcpEventType.TOOL_START in event_types
    assert AcpEventType.TOOL_COMPLETE in event_types
    assert AcpEventType.PLAN_UPDATE in event_types

    # Find and verify the plan update event
    plan_events = [e for e in events if e.event_type == AcpEventType.PLAN_UPDATE]
    assert len(plan_events) == 1
    entries = plan_events[0].data["entries"]
    assert len(entries) == 2
    assert entries[0]["content"] == "Done task"
    assert entries[0]["status"] == "completed"
    assert entries[1]["content"] == "Pending task"
    assert entries[1]["status"] == "pending"
