"""Tests for ACP server integration."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest
from acp import text_block
from acp.schema import AllowedOutcome, RequestPermissionResponse

from steward.acp import DEFAULT_MODE_ID, STEWARD_MODES, StewardAcpAgent
from steward.acp_events import AcpEventQueue, AcpEventType, PermissionResponse
from steward.runner import RunnerResult


class FakeClient:
    def __init__(self) -> None:
        self.updates: List[Dict[str, Any]] = []
        self.permission_requests: List[Dict[str, Any]] = []

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        self.updates.append({"session_id": session_id, "update": update})

    async def request_permission(
        self,
        options: List[Any],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        self.permission_requests.append(
            {
                "options": options,
                "session_id": session_id,
                "tool_call": tool_call,
            }
        )
        return RequestPermissionResponse(outcome=AllowedOutcome(optionId="allow_always", outcome="selected"))


@pytest.mark.asyncio
async def test_acp_prompt_sends_update(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    async def _fake_run(options: Any) -> RunnerResult:
        return RunnerResult(response="ok", messages=[], last_response_id=None)

    monkeypatch.setattr("steward.acp.run_steward_async", _fake_run)

    response = await agent.prompt(prompt=[text_block("hello")], session_id=session.session_id)
    assert response.stop_reason == "end_turn"
    assert client.updates
    assert client.updates[0]["session_id"] == session.session_id


@pytest.mark.asyncio
async def test_acp_load_session_creates_state() -> None:
    agent = StewardAcpAgent()
    await agent.load_session(cwd="/tmp", mcp_servers=[], session_id="abc")
    assert "abc" in agent._sessions


@pytest.mark.asyncio
async def test_acp_cancel_sets_cancellation_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that cancel() properly signals the cancellation token."""
    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    session_id = session.session_id

    # Simulate a prompt in progress by manually setting up the state
    from steward.acp_events import AcpEventQueue, CancellationToken

    state = agent._sessions[session_id]
    state.event_queue = AcpEventQueue(session_id)
    state.cancellation_token = CancellationToken()

    # Cancel should set the token
    assert not state.cancellation_token.is_cancelled
    await agent.cancel(session_id=session_id)
    assert state.cancellation_token.is_cancelled
    assert state.event_queue.is_closed


@pytest.mark.asyncio
async def test_acp_new_session_returns_modes() -> None:
    """Test that new_session returns available modes."""
    agent = StewardAcpAgent()
    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    assert session.modes is not None
    assert session.modes.current_mode_id == DEFAULT_MODE_ID
    assert len(session.modes.available_modes) == len(STEWARD_MODES)
    state = agent._sessions[session.session_id]
    assert state.config.require_permission is True


@pytest.mark.asyncio
async def test_acp_permission_request_prompts_client() -> None:
    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    session_id = session.session_id
    state = agent._sessions[session_id]
    state.event_queue = AcpEventQueue(session_id)

    async def request_and_wait() -> PermissionResponse:
        return await state.event_queue.request_permission(
            tool_call_id="call-1",
            tool_name="bash",
            arguments={"command": "ls"},
            reason="dangerous",
        )

    task = asyncio.create_task(request_and_wait())
    await asyncio.sleep(0.01)
    event = state.event_queue.get_nowait()
    assert event is not None
    assert event.event_type == AcpEventType.PERMISSION_REQUEST

    await agent._send_event_to_client(session_id, event)
    response = await task

    assert response.approved
    assert response.always_allow
    assert client.permission_requests


@pytest.mark.asyncio
async def test_acp_set_session_mode() -> None:
    """Test that set_session_mode updates the session state."""
    agent = StewardAcpAgent()
    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    # Initial mode should be default
    state = agent._sessions[session.session_id]
    assert state.mode_id == "default"

    # Change to plan mode
    response = await agent.set_session_mode(mode_id="plan", session_id=session.session_id)
    assert response is not None
    assert state.mode_id == "plan"


@pytest.mark.asyncio
async def test_acp_plan_mode_adds_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that plan mode adds [[PLAN]] prefix to prompts."""
    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    await agent.set_session_mode(mode_id="plan", session_id=session.session_id)

    captured_options = {}

    async def _fake_run(options: Any) -> RunnerResult:
        captured_options["prompt"] = options.prompt
        return RunnerResult(response="ok", messages=[], last_response_id=None)

    monkeypatch.setattr("steward.acp.run_steward_async", _fake_run)

    await agent.prompt(prompt=[text_block("implement feature X")], session_id=session.session_id)

    assert captured_options["prompt"].startswith("[[PLAN]]")
    assert "implement feature X" in captured_options["prompt"]


def test_acp_configure_session() -> None:
    """Test configure_session updates session config."""
    import asyncio

    agent = StewardAcpAgent()
    session = asyncio.run(agent.new_session(cwd="/tmp", mcp_servers=[]))

    # Configure session
    result = agent.configure_session(
        session.session_id,
        system_prompt="Custom system prompt",
        custom_instructions="Custom instructions",
        max_steps=50,
        timeout_ms=30000,
        retries=3,
        require_permission=True,
    )
    assert result is True

    state = agent._sessions[session.session_id]
    assert state.config.system_prompt == "Custom system prompt"
    assert state.config.custom_instructions == "Custom instructions"
    assert state.config.max_steps == 50
    assert state.config.timeout_ms == 30000
    assert state.config.retries == 3
    assert state.config.require_permission is True


def test_acp_configure_session_unknown_session() -> None:
    """Test configure_session returns False for unknown session."""
    agent = StewardAcpAgent()
    result = agent.configure_session("nonexistent", system_prompt="test")
    assert result is False


@pytest.mark.asyncio
async def test_acp_prompt_uses_session_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that prompt uses session configuration."""
    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    # Configure session
    agent.configure_session(
        session.session_id,
        custom_instructions="Always respond in JSON",
        max_steps=10,
        require_permission=True,
    )

    captured_options = {}

    async def _fake_run(options: Any) -> RunnerResult:
        captured_options["custom_instructions"] = options.custom_instructions
        captured_options["max_steps"] = options.max_steps
        captured_options["require_permission"] = options.require_permission
        return RunnerResult(response="ok", messages=[], last_response_id=None)

    monkeypatch.setattr("steward.acp.run_steward_async", _fake_run)

    await agent.prompt(prompt=[text_block("hello")], session_id=session.session_id)

    assert captured_options["custom_instructions"] == "Always respond in JSON"
    assert captured_options["max_steps"] == 10
    assert captured_options["require_permission"] is True


@pytest.mark.asyncio
async def test_acp_initialize_declares_session_capabilities() -> None:
    """Test that initialize() declares session capabilities."""
    agent = StewardAcpAgent()
    response = await agent.initialize(protocol_version=1)

    caps = response.agent_capabilities
    assert caps is not None
    assert caps.load_session is True
    assert caps.session_capabilities is not None
    assert caps.session_capabilities.list is not None
    assert caps.session_capabilities.fork is not None
    assert caps.session_capabilities.resume is not None


@pytest.mark.asyncio
async def test_acp_list_sessions() -> None:
    """Test list_sessions returns created sessions."""
    agent = StewardAcpAgent(persist_sessions=False)

    # Create some sessions
    s1 = await agent.new_session(cwd="/tmp/project1", mcp_servers=[])
    s2 = await agent.new_session(cwd="/tmp/project2", mcp_servers=[])

    response = await agent.list_sessions()
    assert len(response.sessions) == 2

    session_ids = {s.session_id for s in response.sessions}
    assert s1.session_id in session_ids
    assert s2.session_id in session_ids


@pytest.mark.asyncio
async def test_acp_list_sessions_filter_by_cwd() -> None:
    """Test list_sessions can filter by cwd."""
    agent = StewardAcpAgent(persist_sessions=False)

    await agent.new_session(cwd="/tmp/project1", mcp_servers=[])
    s2 = await agent.new_session(cwd="/tmp/project2", mcp_servers=[])

    response = await agent.list_sessions(cwd="/tmp/project2")
    assert len(response.sessions) == 1
    assert response.sessions[0].session_id == s2.session_id


@pytest.mark.asyncio
async def test_acp_fork_session() -> None:
    """Test fork_session creates a copy of the session."""
    agent = StewardAcpAgent(persist_sessions=False)
    client = FakeClient()
    agent.on_connect(client)

    # Create and configure original session
    original = await agent.new_session(cwd="/tmp/original", mcp_servers=[])
    agent.configure_session(original.session_id, max_steps=20)
    await agent.set_session_mode(mode_id="plan", session_id=original.session_id)

    # Add some history
    state = agent._sessions[original.session_id]
    state.prompt_history = [{"role": "user", "content": "test"}]

    # Fork it
    forked = await agent.fork_session(cwd="/tmp/forked", session_id=original.session_id)

    assert forked.session_id != original.session_id
    assert forked.modes is not None

    # Check forked session has copied state
    forked_state = agent._sessions[forked.session_id]
    assert forked_state.config.max_steps == 20
    assert forked_state.mode_id == "plan"
    assert forked_state.prompt_history == [{"role": "user", "content": "test"}]
    assert forked_state.cwd == "/tmp/forked"

    # Verify independence - modify original
    state.prompt_history.append({"role": "assistant", "content": "response"})
    assert len(forked_state.prompt_history) == 1  # Forked should be unchanged


@pytest.mark.asyncio
async def test_acp_resume_session() -> None:
    """Test resume_session loads an existing session."""
    agent = StewardAcpAgent(persist_sessions=False)

    # Create a session
    original = await agent.new_session(cwd="/tmp/project", mcp_servers=[])
    agent.configure_session(original.session_id, max_steps=15)

    # When session is already in memory, resume just returns it
    response = await agent.resume_session(cwd="/tmp/new_cwd", session_id=original.session_id)
    assert response.modes is not None

    # State is preserved, cwd unchanged (since session was in memory)
    state = agent._sessions[original.session_id]
    assert state.config.max_steps == 15
    assert state.cwd == "/tmp/project"  # Original cwd kept


@pytest.mark.asyncio
async def test_acp_resume_session_creates_new_if_not_found() -> None:
    """Test resume_session creates new session if not found."""
    agent = StewardAcpAgent(persist_sessions=False)

    # Resume a non-existent session
    response = await agent.resume_session(cwd="/tmp/new_project", session_id="nonexistent-id")
    assert response.modes is not None

    # New session should be created
    state = agent._sessions["nonexistent-id"]
    assert state.cwd == "/tmp/new_project"
    assert state.mode_id == "default"


@pytest.mark.asyncio
async def test_acp_session_persistence(tmp_path: Any) -> None:
    """Test session state is persisted to disk."""
    from steward.acp import StewardAcpAgent

    agent = StewardAcpAgent(persist_sessions=True)
    agent._session_dir = tmp_path

    # Create and configure session
    session = await agent.new_session(cwd="/tmp/test", mcp_servers=[])
    agent.configure_session(session.session_id, max_steps=25, custom_instructions="Be helpful")
    await agent.set_session_model(model_id="gpt-4", session_id=session.session_id)

    # Check file was created
    state_file = tmp_path / session.session_id / "acp_state.json"
    assert state_file.exists()

    # Create new agent and load the session
    agent2 = StewardAcpAgent(persist_sessions=True)
    agent2._session_dir = tmp_path

    await agent2.load_session(cwd="/tmp/test", mcp_servers=[], session_id=session.session_id)

    # Verify state was loaded
    state = agent2._sessions[session.session_id]
    assert state.config.max_steps == 25
    assert state.config.custom_instructions == "Be helpful"
    assert state.model_id == "gpt-4"


@pytest.mark.asyncio
async def test_acp_initialize_declares_mcp_capabilities() -> None:
    """Test that initialize() declares MCP capabilities."""
    agent = StewardAcpAgent()
    response = await agent.initialize(protocol_version=1)

    caps = response.agent_capabilities
    assert caps is not None
    assert caps.mcp_capabilities is not None
    # We don't support HTTP/SSE yet
    assert caps.mcp_capabilities.http is False
    assert caps.mcp_capabilities.sse is False


@pytest.mark.asyncio
async def test_acp_new_session_parses_mcp_servers() -> None:
    """Test that new_session parses MCP server configs."""
    from acp.schema import McpServerStdio

    agent = StewardAcpAgent(persist_sessions=False)

    # Create session with MCP servers
    mcp_servers = [
        McpServerStdio(command="python", args=["-m", "my_mcp_server"], env=[], name="test-server"),
    ]
    session = await agent.new_session(cwd="/tmp/test", mcp_servers=mcp_servers)

    state = agent._sessions[session.session_id]
    assert len(state.mcp_servers) == 1
    assert state.mcp_servers[0].server_type == "stdio"
    assert state.mcp_servers[0].command == "python"
    assert state.mcp_servers[0].args == ["-m", "my_mcp_server"]
    assert state.mcp_servers[0].name == "test-server"


@pytest.mark.asyncio
async def test_acp_load_session_updates_mcp_servers() -> None:
    """Test that load_session updates MCP servers for existing session."""
    from acp.schema import McpServerStdio

    agent = StewardAcpAgent(persist_sessions=False)

    # Create session without MCP servers
    session = await agent.new_session(cwd="/tmp/test", mcp_servers=[])
    assert len(agent._sessions[session.session_id].mcp_servers) == 0

    # Load with MCP servers - should update
    mcp_servers = [
        McpServerStdio(command="node", args=["server.js"], env=[], name="node-server"),
    ]
    await agent.load_session(cwd="/tmp/test", mcp_servers=mcp_servers, session_id=session.session_id)

    state = agent._sessions[session.session_id]
    assert len(state.mcp_servers) == 1
    assert state.mcp_servers[0].command == "node"


def test_acp_parse_mcp_servers_dict_format() -> None:
    """Test parsing MCP servers from dict format."""
    from steward.acp import _parse_mcp_servers

    servers = [
        {"command": "python", "args": ["-m", "server"], "name": "my-server"},
        {"url": "http://localhost:8080", "name": "http-server"},
    ]
    specs = _parse_mcp_servers(servers)  # type: ignore

    assert len(specs) == 2
    assert specs[0].name == "my-server"
    assert specs[0].server_type == "stdio"
    assert specs[0].command == "python"
    assert specs[1].name == "http-server"
    assert specs[1].server_type == "http"
    assert specs[1].url == "http://localhost:8080"


@pytest.mark.asyncio
async def test_acp_mcp_servers_persisted(tmp_path: Any) -> None:
    """Test MCP servers are persisted with session."""
    from acp.schema import McpServerStdio

    from steward.acp import StewardAcpAgent

    agent = StewardAcpAgent(persist_sessions=True)
    agent._session_dir = tmp_path

    mcp_servers = [
        McpServerStdio(command="python", args=["-m", "server"], env=[], name="persisted-server"),
    ]
    session = await agent.new_session(cwd="/tmp/test", mcp_servers=mcp_servers)

    # Verify initial state
    state = agent._sessions[session.session_id]
    assert len(state.mcp_servers) == 1
    assert state.mcp_servers[0].command == "python"

    # Load in new agent with same MCP servers (simulating client reconnect)
    agent2 = StewardAcpAgent(persist_sessions=True)
    agent2._session_dir = tmp_path
    await agent2.load_session(
        cwd="/tmp/test",
        mcp_servers=mcp_servers,  # Pass the same servers
        session_id=session.session_id,
    )

    # MCP servers should be present (from the load call)
    state2 = agent2._sessions[session.session_id]
    assert len(state2.mcp_servers) == 1
    assert state2.mcp_servers[0].command == "python"
    assert state2.mcp_servers[0].name == "persisted-server"
    # Other state should be preserved from disk
    assert state2.mode_id == "default"


@pytest.mark.asyncio
async def test_acp_thought_streaming() -> None:
    """Test thought events are sent to client."""
    from steward.acp import StewardAcpAgent
    from steward.acp_events import AcpEventQueue

    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    session_id = session.session_id

    # Create event queue and set up session state
    event_queue = AcpEventQueue(session_id)
    state = agent._sessions[session_id]
    state.event_queue = event_queue

    # Emit thought event
    await event_queue.emit_thought("Analyzing the codebase...")
    event = await event_queue.get()

    # Send to client
    await agent._send_event_to_client(session_id, event)

    # Verify client received thought chunk (ignore available_commands update)
    updates = [u["update"] for u in client.updates if u["update"].sessionUpdate == "agent_thought_chunk"]
    assert len(updates) == 1
    update = updates[0]
    assert update.sessionUpdate == "agent_thought_chunk"
    assert update.content.text == "Analyzing the codebase..."


@pytest.mark.asyncio
async def test_acp_plan_update_streaming() -> None:
    """Test plan update events are sent to client."""
    from steward.acp import StewardAcpAgent
    from steward.acp_events import AcpEventQueue

    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    session_id = session.session_id

    # Create event queue and set up session state
    event_queue = AcpEventQueue(session_id)
    state = agent._sessions[session_id]
    state.event_queue = event_queue

    # Emit plan update event
    plan_entries = [
        {"content": "Implement feature A", "status": "completed", "priority": "high"},
        {"content": "Write tests", "status": "pending", "priority": "medium"},
        {"content": "Update docs", "status": "pending", "priority": "low"},
    ]
    await event_queue.emit_plan_update(plan_entries)
    event = await event_queue.get()

    # Send to client
    await agent._send_event_to_client(session_id, event)

    # Verify client received plan update (ignore available_commands update)
    updates = [u["update"] for u in client.updates if u["update"].sessionUpdate == "plan"]
    assert len(updates) == 1
    update = updates[0]
    assert update.sessionUpdate == "plan"
    assert len(update.entries) == 3
    assert update.entries[0].content == "Implement feature A"
    assert update.entries[0].status == "completed"
    assert update.entries[0].priority == "high"
    assert update.entries[1].content == "Write tests"
    assert update.entries[1].status == "pending"


@pytest.mark.asyncio
async def test_acp_client_filesystem_capabilities() -> None:
    """Test that client filesystem capabilities are captured from initialize."""
    from acp.schema import ClientCapabilities, FileSystemCapability

    from steward.acp import StewardAcpAgent

    agent = StewardAcpAgent()

    # Without capabilities
    await agent.initialize(protocol_version=1, client_capabilities=None)
    assert agent._client_fs.read_text_file is False
    assert agent._client_fs.write_text_file is False

    # With capabilities (using 'fs' which is the actual attribute name)
    client_caps = ClientCapabilities(fs=FileSystemCapability(readTextFile=True, writeTextFile=True))
    await agent.initialize(protocol_version=1, client_capabilities=client_caps)
    assert agent._client_fs.read_text_file is True
    assert agent._client_fs.write_text_file is True


@pytest.mark.asyncio
async def test_acp_delegated_file_read() -> None:
    """Test delegated file read via client."""
    from steward.acp import StewardAcpAgent

    class FileClient(FakeClient):
        async def read_text_file(self, path: str, session_id: str, **kwargs: Any) -> Any:
            class Response:
                content = f"content of {path}"

            return Response()

    agent = StewardAcpAgent()
    client = FileClient()
    agent.on_connect(client)

    # Enable delegation
    agent._client_fs.read_text_file = True

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    # Read via delegation
    content = await agent.read_file_delegated(session.session_id, "/test/file.txt")
    assert content == "content of /test/file.txt"


@pytest.mark.asyncio
async def test_acp_delegated_file_read_fallback() -> None:
    """Test that delegated read returns None when not supported."""
    from steward.acp import StewardAcpAgent

    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    # Delegation not enabled
    assert agent._client_fs.read_text_file is False

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    content = await agent.read_file_delegated(session.session_id, "/test/file.txt")
    assert content is None


@pytest.mark.asyncio
async def test_acp_delegated_file_write() -> None:
    """Test delegated file write via client."""
    from steward.acp import StewardAcpAgent

    class FileClient(FakeClient):
        written: Dict[str, str] = {}

        async def write_text_file(self, path: str, session_id: str, content: str, **kwargs: Any) -> Any:
            self.written[path] = content
            return None

    agent = StewardAcpAgent()
    client = FileClient()
    agent.on_connect(client)

    # Enable delegation
    agent._client_fs.write_text_file = True

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    # Write via delegation
    success = await agent.write_file_delegated(session.session_id, "/test/output.txt", "hello world")
    assert success is True
    assert client.written["/test/output.txt"] == "hello world"


@pytest.mark.asyncio
async def test_acp_delegated_file_write_fallback() -> None:
    """Test that delegated write returns False when not supported."""
    from steward.acp import StewardAcpAgent

    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    # Delegation not enabled
    assert agent._client_fs.write_text_file is False

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])
    success = await agent.write_file_delegated(session.session_id, "/test/file.txt", "content")
    assert success is False


@pytest.mark.asyncio
async def test_acp_supports_delegated_methods() -> None:
    """Test helper methods for checking delegation support."""
    from steward.acp import StewardAcpAgent

    agent = StewardAcpAgent()

    # Initially no support
    assert agent.supports_delegated_read() is False
    assert agent.supports_delegated_write() is False

    # Enable read only
    agent._client_fs.read_text_file = True
    assert agent.supports_delegated_read() is True
    assert agent.supports_delegated_write() is False

    # Enable write
    agent._client_fs.write_text_file = True
    assert agent.supports_delegated_read() is True
    assert agent.supports_delegated_write() is True
