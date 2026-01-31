"""ACP event infrastructure for streaming updates and tool visibility.

Provides asyncio-based event queuing for:
- Streaming text responses
- Tool call start/progress/completion
- Permission requests
- Cancellation support

Designed to support parallel requests and sub-agents.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional


class AcpEventType(str, Enum):
    """Types of events that can be emitted to ACP clients."""

    # Text streaming
    TEXT_CHUNK = "text_chunk"
    TEXT_DONE = "text_done"

    # Tool lifecycle
    TOOL_START = "tool_start"
    TOOL_PROGRESS = "tool_progress"
    TOOL_COMPLETE = "tool_complete"
    TOOL_FAILED = "tool_failed"

    # Agent reasoning
    THOUGHT_CHUNK = "thought_chunk"

    # Plan updates
    PLAN_UPDATE = "plan_update"

    # Permission requests
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_RESPONSE = "permission_response"

    # Control
    CANCEL = "cancel"
    ERROR = "error"


# ACP tool kind mapping from Steward tool names
TOOL_KIND_MAP: Dict[str, Literal["read", "edit", "delete", "move", "search", "execute", "think", "fetch", "switch_mode", "other"]] = {
    # Read operations
    "view": "read",
    "grep": "search",
    "glob": "search",
    "git_status": "read",
    "git_diff": "read",
    "get_changed_files": "read",
    "list_bash": "read",
    "list_memories": "read",
    "list_code_usages": "search",
    "workspace_summary": "read",
    "mcp_list_servers": "read",
    "mcp_list_tools": "read",
    "get_python_executable_details": "read",
    # Edit operations
    "edit": "edit",
    "create": "edit",
    "replace_string_in_file": "edit",
    "multi_replace_string_in_file": "edit",
    "apply_patch": "edit",
    "mkdir": "edit",
    # Execute operations
    "bash": "execute",
    "read_bash": "execute",
    "write_bash": "execute",
    "stop_bash": "execute",
    "run_js": "execute",
    "git_commit": "execute",
    "git_stash": "execute",
    "install_python_packages": "execute",
    "configure_python_environment": "execute",
    "mcp_call": "execute",
    # Fetch operations
    "web_fetch": "fetch",
    "web_search": "fetch",
    # Think/plan operations
    "report_intent": "think",
    "update_todo": "think",
    "store_memory": "think",
    "load_skill": "read",
    "discover_skills": "search",
    "suggest_skills": "search",
    # User interaction
    "ask_user": "other",
}

# Tools that require permission before execution
DANGEROUS_TOOLS = frozenset({
    "bash",
    "write_bash",
    "edit",
    "create",
    "replace_string_in_file",
    "multi_replace_string_in_file",
    "apply_patch",
    "git_commit",
    "install_python_packages",
    "run_js",
})


def get_tool_kind(tool_name: str) -> Literal["read", "edit", "delete", "move", "search", "execute", "think", "fetch", "switch_mode", "other"]:
    """Map Steward tool name to ACP tool kind."""
    return TOOL_KIND_MAP.get(tool_name, "other")


def is_dangerous_tool(tool_name: str) -> bool:
    """Check if a tool requires permission before execution."""
    return tool_name in DANGEROUS_TOOLS


@dataclass
class AcpEvent:
    """Base event structure for ACP updates."""

    event_type: AcpEventType
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    tool_call_id: Optional[str] = None
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0.0)


@dataclass
class ToolCallEvent(AcpEvent):
    """Event for tool call lifecycle updates."""

    tool_name: str = ""
    tool_kind: Literal["read", "edit", "delete", "move", "search", "execute", "think", "fetch", "switch_mode", "other"] = "other"
    arguments: Dict[str, Any] = field(default_factory=dict)
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PermissionRequest:
    """Request for user permission before executing a tool."""

    request_id: str
    session_id: str
    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    reason: str = ""


@dataclass
class PermissionResponse:
    """Response to a permission request."""

    request_id: str
    approved: bool
    always_allow: bool = False  # Remember this permission for the session


class CancellationToken:
    """Token to signal cancellation of an operation."""

    def __init__(self) -> None:
        self._cancelled = False
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Signal cancellation."""
        self._cancelled = True
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    async def wait(self) -> None:
        """Wait until cancellation is signalled."""
        await self._event.wait()

    def check(self) -> None:
        """Raise CancelledError if cancelled."""
        if self._cancelled:
            raise asyncio.CancelledError("Operation cancelled by user")


class AcpEventQueue:
    """Async queue for ACP events with support for multiple consumers.

    Designed for:
    - Parallel tool execution with ordered event delivery
    - Sub-agent event aggregation
    - Cancellation propagation
    """

    def __init__(self, session_id: str, maxsize: int = 0) -> None:
        self.session_id = session_id
        self._queue: asyncio.Queue[AcpEvent] = asyncio.Queue(maxsize=maxsize)
        self._cancellation = CancellationToken()
        self._closed = False
        self._pending_permissions: Dict[str, asyncio.Future[PermissionResponse]] = {}
        self._granted_permissions: set[str] = set()  # Tools with "always allow"

    async def put(self, event: AcpEvent) -> None:
        """Add an event to the queue."""
        if self._closed:
            return
        event.session_id = self.session_id
        await self._queue.put(event)

    async def get(self) -> AcpEvent:
        """Get the next event from the queue."""
        return await self._queue.get()

    def get_nowait(self) -> Optional[AcpEvent]:
        """Get an event without waiting, returns None if empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def drain(self) -> List[AcpEvent]:
        """Get all currently queued events."""
        events = []
        while True:
            event = self.get_nowait()
            if event is None:
                break
            events.append(event)
        return events

    def close(self) -> None:
        """Close the queue, no more events will be accepted."""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        """Check if the queue is closed."""
        return self._closed

    @property
    def cancellation(self) -> CancellationToken:
        """Get the cancellation token for this queue."""
        return self._cancellation

    def cancel(self) -> None:
        """Cancel all operations associated with this queue."""
        self._cancellation.cancel()
        self.close()

    # Permission handling

    async def request_permission(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: str = "",
    ) -> PermissionResponse:
        """Request permission for a tool execution.

        Returns immediately if permission was previously granted with "always allow".
        Otherwise, emits a permission request event and waits for response.
        """
        # Check if already granted
        if tool_name in self._granted_permissions:
            return PermissionResponse(
                request_id="",
                approved=True,
                always_allow=True,
            )

        request_id = str(uuid.uuid4())
        # PermissionRequest is created for documentation but data is sent via event
        _ = PermissionRequest(
            request_id=request_id,
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
        )

        # Create future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future[PermissionResponse] = loop.create_future()
        self._pending_permissions[request_id] = future

        # Emit permission request event
        await self.put(AcpEvent(
            event_type=AcpEventType.PERMISSION_REQUEST,
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            data={
                "request_id": request_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "reason": reason,
            },
        ))

        try:
            # Wait for response (with cancellation support)
            async def wait_for_future() -> PermissionResponse:
                return await asyncio.wrap_future(asyncio.ensure_future(
                    asyncio.get_event_loop().run_in_executor(None, future.result)
                )) if False else await asyncio.shield(asyncio.ensure_future(self._wait_for_permission(future)))

            # Simple approach: wait for either the future or cancellation
            wait_task = asyncio.create_task(self._wait_for_permission(future))
            cancel_task = asyncio.create_task(self._cancellation.wait())

            done, pending = await asyncio.wait(
                [wait_task, cancel_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if self._cancellation.is_cancelled:
                raise asyncio.CancelledError("Operation cancelled")

            response = wait_task.result()

            # Remember "always allow" grants
            if response.approved and response.always_allow:
                self._granted_permissions.add(tool_name)

            return response
        finally:
            self._pending_permissions.pop(request_id, None)

    async def _wait_for_permission(self, future: "asyncio.Future[PermissionResponse]") -> PermissionResponse:
        """Wait for a permission future to complete."""
        while not future.done():
            await asyncio.sleep(0.01)
        return future.result()

    def resolve_permission(self, request_id: str, response: PermissionResponse) -> bool:
        """Resolve a pending permission request.

        Returns True if the request was found and resolved, False otherwise.
        """
        future = self._pending_permissions.get(request_id)
        if future is None:
            return False
        if not future.done():
            future.set_result(response)
        return True

    # Convenience methods for common events

    async def emit_text_chunk(self, text: str) -> None:
        """Emit a text streaming chunk."""
        await self.put(AcpEvent(
            event_type=AcpEventType.TEXT_CHUNK,
            session_id=self.session_id,
            data={"text": text},
        ))

    async def emit_text_done(self) -> None:
        """Emit text streaming completion."""
        await self.put(AcpEvent(
            event_type=AcpEventType.TEXT_DONE,
            session_id=self.session_id,
        ))

    async def emit_tool_start(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        """Emit tool call start event."""
        await self.put(ToolCallEvent(
            event_type=AcpEventType.TOOL_START,
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=get_tool_kind(tool_name),
            arguments=arguments,
            status="in_progress",
        ))

    async def emit_tool_progress(
        self,
        tool_call_id: str,
        tool_name: str,
        status: Literal["pending", "in_progress", "completed", "failed"] = "in_progress",
        output: Optional[str] = None,
    ) -> None:
        """Emit tool call progress update."""
        await self.put(ToolCallEvent(
            event_type=AcpEventType.TOOL_PROGRESS,
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=get_tool_kind(tool_name),
            status=status,
            output=output,
        ))

    async def emit_tool_complete(
        self,
        tool_call_id: str,
        tool_name: str,
        output: str,
    ) -> None:
        """Emit tool call completion event."""
        await self.put(ToolCallEvent(
            event_type=AcpEventType.TOOL_COMPLETE,
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=get_tool_kind(tool_name),
            status="completed",
            output=output,
        ))

    async def emit_tool_failed(
        self,
        tool_call_id: str,
        tool_name: str,
        error: str,
    ) -> None:
        """Emit tool call failure event."""
        await self.put(ToolCallEvent(
            event_type=AcpEventType.TOOL_FAILED,
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=get_tool_kind(tool_name),
            status="failed",
            error=error,
        ))

    async def emit_thought(self, text: str) -> None:
        """Emit agent thought/reasoning chunk."""
        await self.put(AcpEvent(
            event_type=AcpEventType.THOUGHT_CHUNK,
            session_id=self.session_id,
            data={"text": text},
        ))

    async def emit_plan_update(self, entries: List[Dict[str, Any]]) -> None:
        """Emit plan/TODO update."""
        await self.put(AcpEvent(
            event_type=AcpEventType.PLAN_UPDATE,
            session_id=self.session_id,
            data={"entries": entries},
        ))

    async def emit_error(self, error: str, fatal: bool = False) -> None:
        """Emit an error event."""
        await self.put(AcpEvent(
            event_type=AcpEventType.ERROR,
            session_id=self.session_id,
            data={"error": error, "fatal": fatal},
        ))


# Type for event handler callbacks
AcpEventHandler = Callable[[AcpEvent], Awaitable[None]]


class AcpEventDispatcher:
    """Dispatches events from queue to ACP client.

    Runs as a background task, consuming events and sending updates to the client.
    Supports multiple concurrent queues for sub-agents.
    """

    def __init__(self, send_update: AcpEventHandler) -> None:
        self._send_update = send_update
        self._queues: Dict[str, AcpEventQueue] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    def create_queue(self, session_id: str) -> AcpEventQueue:
        """Create a new event queue for a session."""
        if session_id in self._queues:
            return self._queues[session_id]
        queue = AcpEventQueue(session_id)
        self._queues[session_id] = queue
        return queue

    def get_queue(self, session_id: str) -> Optional[AcpEventQueue]:
        """Get an existing queue for a session."""
        return self._queues.get(session_id)

    async def start(self, session_id: str) -> None:
        """Start dispatching events for a session."""
        queue = self._queues.get(session_id)
        if queue is None:
            return

        async def dispatch_loop() -> None:
            while not queue.is_closed or not queue._queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    await self._send_update(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception:
                    # Log but don't crash the dispatcher
                    pass

        task = asyncio.create_task(dispatch_loop())
        self._tasks[session_id] = task

    async def stop(self, session_id: str) -> None:
        """Stop dispatching events for a session."""
        queue = self._queues.get(session_id)
        if queue:
            queue.close()

        task = self._tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._queues.pop(session_id, None)

    def cancel(self, session_id: str) -> None:
        """Cancel operations for a session."""
        queue = self._queues.get(session_id)
        if queue:
            queue.cancel()
