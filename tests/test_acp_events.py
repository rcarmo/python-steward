"""Tests for ACP event infrastructure."""

from __future__ import annotations

import asyncio

import pytest

from steward.acp_events import (
    AcpEvent,
    AcpEventQueue,
    AcpEventType,
    CancellationToken,
    PermissionResponse,
    ToolCallEvent,
    get_tool_kind,
    is_dangerous_tool,
)


class TestCancellationToken:
    """Tests for CancellationToken."""

    def test_initial_state(self) -> None:
        token = CancellationToken()
        assert not token.is_cancelled

    def test_cancel(self) -> None:
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    def test_check_raises_when_cancelled(self) -> None:
        token = CancellationToken()
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            token.check()

    def test_check_does_not_raise_when_not_cancelled(self) -> None:
        token = CancellationToken()
        token.check()  # Should not raise

    @pytest.mark.asyncio
    async def test_wait_returns_when_cancelled(self) -> None:
        token = CancellationToken()

        async def cancel_after_delay() -> None:
            await asyncio.sleep(0.01)
            token.cancel()

        task = asyncio.create_task(cancel_after_delay())
        await token.wait()
        assert token.is_cancelled
        await task


class TestAcpEventQueue:
    """Tests for AcpEventQueue."""

    @pytest.mark.asyncio
    async def test_put_and_get(self) -> None:
        queue = AcpEventQueue("test-session")
        event = AcpEvent(
            event_type=AcpEventType.TEXT_CHUNK,
            session_id="test-session",
            data={"text": "hello"},
        )
        await queue.put(event)
        retrieved = await queue.get()
        assert retrieved.event_type == AcpEventType.TEXT_CHUNK
        assert retrieved.data["text"] == "hello"

    @pytest.mark.asyncio
    async def test_get_nowait_empty(self) -> None:
        queue = AcpEventQueue("test-session")
        result = queue.get_nowait()
        assert result is None

    @pytest.mark.asyncio
    async def test_drain(self) -> None:
        queue = AcpEventQueue("test-session")
        for i in range(3):
            await queue.put(AcpEvent(
                event_type=AcpEventType.TEXT_CHUNK,
                session_id="test-session",
                data={"text": f"chunk-{i}"},
            ))
        events = await queue.drain()
        assert len(events) == 3
        assert events[0].data["text"] == "chunk-0"
        assert events[2].data["text"] == "chunk-2"

    @pytest.mark.asyncio
    async def test_close_stops_accepting_events(self) -> None:
        queue = AcpEventQueue("test-session")
        queue.close()
        assert queue.is_closed
        # Put should silently return without queueing
        await queue.put(AcpEvent(
            event_type=AcpEventType.TEXT_CHUNK,
            session_id="test-session",
            data={},
        ))
        assert queue.get_nowait() is None

    @pytest.mark.asyncio
    async def test_cancel_sets_token_and_closes(self) -> None:
        queue = AcpEventQueue("test-session")
        assert not queue.cancellation.is_cancelled
        assert not queue.is_closed
        queue.cancel()
        assert queue.cancellation.is_cancelled
        assert queue.is_closed

    @pytest.mark.asyncio
    async def test_emit_text_chunk(self) -> None:
        queue = AcpEventQueue("test-session")
        await queue.emit_text_chunk("hello world")
        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == AcpEventType.TEXT_CHUNK
        assert event.data["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_emit_tool_lifecycle(self) -> None:
        queue = AcpEventQueue("test-session")

        # Start
        await queue.emit_tool_start("call-1", "view", {"path": "/test"})
        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == AcpEventType.TOOL_START
        assert event.tool_call_id == "call-1"

        # Progress
        await queue.emit_tool_progress("call-1", "view", "in_progress", "Reading...")
        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == AcpEventType.TOOL_PROGRESS

        # Complete
        await queue.emit_tool_complete("call-1", "view", "file contents")
        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == AcpEventType.TOOL_COMPLETE

    @pytest.mark.asyncio
    async def test_emit_tool_failed(self) -> None:
        queue = AcpEventQueue("test-session")
        await queue.emit_tool_failed("call-1", "bash", "command not found")
        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == AcpEventType.TOOL_FAILED
        assert isinstance(event, ToolCallEvent)
        assert event.error == "command not found"


class TestPermissions:
    """Tests for permission handling."""

    @pytest.mark.asyncio
    async def test_permission_granted_immediately_when_always_allowed(self) -> None:
        queue = AcpEventQueue("test-session")
        # Pre-grant permission
        queue._granted_permissions.add("bash")

        response = await queue.request_permission(
            tool_call_id="call-1",
            tool_name="bash",
            arguments={"command": "ls"},
        )
        assert response.approved
        assert response.always_allow
        # No event should be emitted
        assert queue.get_nowait() is None

    @pytest.mark.asyncio
    async def test_resolve_permission(self) -> None:
        queue = AcpEventQueue("test-session")

        # Start permission request in background
        async def request_and_wait() -> PermissionResponse:
            return await queue.request_permission(
                tool_call_id="call-1",
                tool_name="bash",
                arguments={"command": "rm -rf /"},
                reason="dangerous",
            )

        task = asyncio.create_task(request_and_wait())

        # Wait for the request event
        await asyncio.sleep(0.01)
        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == AcpEventType.PERMISSION_REQUEST
        request_id = event.data["request_id"]

        # Resolve the permission
        resolved = queue.resolve_permission(
            request_id,
            PermissionResponse(request_id=request_id, approved=True, always_allow=True),
        )
        assert resolved

        response = await task
        assert response.approved
        assert response.always_allow

        # Should now be in granted permissions
        assert "bash" in queue._granted_permissions

    @pytest.mark.asyncio
    async def test_resolve_unknown_permission_returns_false(self) -> None:
        queue = AcpEventQueue("test-session")
        result = queue.resolve_permission(
            "unknown-id",
            PermissionResponse(request_id="unknown-id", approved=True),
        )
        assert not result


class TestToolKindMapping:
    """Tests for tool kind mapping."""

    def test_read_tools(self) -> None:
        assert get_tool_kind("view") == "read"
        assert get_tool_kind("git_status") == "read"

    def test_search_tools(self) -> None:
        assert get_tool_kind("grep") == "search"
        assert get_tool_kind("glob") == "search"

    def test_edit_tools(self) -> None:
        assert get_tool_kind("edit") == "edit"
        assert get_tool_kind("create") == "edit"

    def test_execute_tools(self) -> None:
        assert get_tool_kind("bash") == "execute"
        assert get_tool_kind("run_js") == "execute"

    def test_fetch_tools(self) -> None:
        assert get_tool_kind("web_fetch") == "fetch"
        assert get_tool_kind("web_search") == "fetch"

    def test_think_tools(self) -> None:
        assert get_tool_kind("report_intent") == "think"
        assert get_tool_kind("update_todo") == "think"

    def test_unknown_tool_returns_other(self) -> None:
        assert get_tool_kind("unknown_tool_xyz") == "other"


class TestDangerousTools:
    """Tests for dangerous tool identification."""

    def test_dangerous_tools(self) -> None:
        assert is_dangerous_tool("bash")
        assert is_dangerous_tool("edit")
        assert is_dangerous_tool("create")
        assert is_dangerous_tool("git_commit")

    def test_safe_tools(self) -> None:
        assert not is_dangerous_tool("view")
        assert not is_dangerous_tool("grep")
        assert not is_dangerous_tool("glob")
        assert not is_dangerous_tool("git_status")
