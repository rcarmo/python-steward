"""ACP server for Steward."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AuthenticateResponse,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    SetSessionModelResponse,
    SetSessionModeResponse,
    run_agent,
    start_tool_call,
    text_block,
    update_agent_message,
    update_tool_call,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AgentPlanUpdate,
    AgentThoughtChunk,
    AvailableCommand,
    AvailableCommandsUpdate,
    AudioContentBlock,
    ClientCapabilities,
    EmbeddedResourceContentBlock,
    SessionInfoUpdate,
    FileSystemCapability,
    ForkSessionResponse,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    ListSessionsResponse,
    McpCapabilities,
    McpServerStdio,
    PlanEntry,
    ResourceContentBlock,
    ResumeSessionResponse,
    SessionCapabilities,
    SessionForkCapabilities,
    SessionInfo,
    SessionListCapabilities,
    SessionMode,
    SessionModeState,
    SessionResumeCapabilities,
    SseMcpServer,
    TextContentBlock,
)

from .acp_events import AcpEvent, AcpEventQueue, AcpEventType, CancellationToken, PermissionResponse
from .config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, PLAN_MODE_PREFIX, detect_provider
from .logger import HumanEntry, Logger
from .runner import RunnerOptions, run_steward_async
from .session import DEFAULT_SESSION_DIR, generate_session_id
from .tools import discover_tools
from .utils import get_version

# Supported modes for Steward
STEWARD_MODES = [
    {"id": "default", "name": "Default", "description": "Standard agent mode with full tool access"},
    {"id": "plan", "name": "Plan Mode", "description": "Create implementation plans without executing changes"},
    {"id": "code-review", "name": "Code Review", "description": "Review code changes with high signal-to-noise ratio"},
]

DEFAULT_MODE_ID = "default"


@dataclass
class SessionConfig:
    """Configuration options for a session, matching REPL capabilities."""

    system_prompt: Optional[str] = None
    custom_instructions: Optional[str] = None
    max_steps: Optional[int] = None
    timeout_ms: Optional[int] = None
    retries: Optional[int] = None
    require_permission: bool = False


@dataclass
class McpServerSpec:
    """MCP server specification from ACP."""

    name: str
    server_type: str  # "stdio", "http", "sse"
    # Stdio servers
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    # HTTP/SSE servers
    url: Optional[str] = None


@dataclass
class ClientFileSystemCapabilities:
    """Track client's file system capabilities."""

    read_text_file: bool = False
    write_text_file: bool = False


@dataclass
class SessionState:
    """State for an ACP session."""

    prompt_history: List[Dict[str, Any]] = field(default_factory=list)
    last_response_id: Optional[str] = None
    model_id: Optional[str] = None
    mode_id: Optional[str] = None
    cwd: str = ""  # Working directory for the session
    title: Optional[str] = None  # Human-readable session title
    updated_at: Optional[str] = None  # Last update timestamp
    # Session configuration (parity with REPL)
    config: SessionConfig = field(default_factory=SessionConfig)
    # MCP servers passed from ACP client
    mcp_servers: List[McpServerSpec] = field(default_factory=list)
    # ACP event infrastructure
    event_queue: Optional[AcpEventQueue] = None
    cancellation_token: Optional[CancellationToken] = None
    # Active prompt task for cancellation
    _prompt_task: Optional[asyncio.Task] = field(default=None, repr=False)


class StewardAcpAgent(Agent):
    """ACP agent implementation for Steward.

    Provides streaming updates, tool visibility, permission requests,
    and cancellation support via asyncio event queues.
    """

    _conn: Client
    _client_fs: ClientFileSystemCapabilities
    _logger: Logger

    def __init__(self, persist_sessions: bool = True) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._persist_sessions = persist_sessions
        self._session_dir = DEFAULT_SESSION_DIR
        self._client_fs = ClientFileSystemCapabilities()
        self._logger = Logger(provider="acp", model="unknown", enable_file_logs=False)

    def on_connect(self, conn: Client) -> None:
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        # Store client filesystem capabilities for delegation
        if client_capabilities and client_capabilities.fs:
            fs = client_capabilities.fs
            self._client_fs = ClientFileSystemCapabilities(
                read_text_file=bool(getattr(fs, "readTextFile", False) or getattr(fs, "read_text_file", False)),
                write_text_file=bool(getattr(fs, "writeTextFile", False) or getattr(fs, "write_text_file", False)),
            )
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(
                load_session=True,
                mcp_capabilities=McpCapabilities(
                    http=False,  # Not yet supported
                    sse=False,   # Not yet supported
                ),
                session_capabilities=SessionCapabilities(
                    list=SessionListCapabilities(),
                    fork=SessionForkCapabilities(),
                    resume=SessionResumeCapabilities(),
                ),
            ),
            agent_info=Implementation(name="steward", title="Steward", version=get_version()),
        )

    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        return AuthenticateResponse()

    async def new_session(
        self, cwd: str, mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio], **kwargs: Any
    ) -> NewSessionResponse:
        session_id = generate_session_id()
        mcp_specs = _parse_mcp_servers(mcp_servers)
        state = SessionState(
            mode_id=DEFAULT_MODE_ID,
            cwd=cwd,
            updated_at=_utc_now_iso(),
            mcp_servers=mcp_specs,
        )
        self._sessions[session_id] = state
        if self._persist_sessions:
            self._save_session(session_id, state)
        await self._send_available_commands(session_id)
        return NewSessionResponse(
            session_id=session_id,
            modes=_build_mode_state(DEFAULT_MODE_ID),
        )

    async def load_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
        session_id: str,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        # Try to load from disk first
        if self._persist_sessions and session_id not in self._sessions:
            loaded = self._load_session(session_id)
            if loaded:
                self._sessions[session_id] = loaded
        # Create new if not found
        if session_id not in self._sessions:
            mcp_specs = _parse_mcp_servers(mcp_servers)
            self._sessions[session_id] = SessionState(
                mode_id=DEFAULT_MODE_ID,
                cwd=cwd,
                updated_at=_utc_now_iso(),
                mcp_servers=mcp_specs,
            )
        else:
            # Update MCP servers if session already exists
            state = self._sessions[session_id]
            state.mcp_servers = _parse_mcp_servers(mcp_servers)
        await self._send_available_commands(session_id)
        return LoadSessionResponse()

    async def list_sessions(
        self, cursor: str | None = None, cwd: str | None = None, **kwargs: Any
    ) -> ListSessionsResponse:
        """List all available sessions."""
        sessions: List[SessionInfo] = []

        # Include in-memory sessions
        for sid, state in self._sessions.items():
            if cwd is None or state.cwd == cwd:
                sessions.append(SessionInfo(
                    session_id=sid,
                    cwd=state.cwd or "",
                    title=state.title,
                    updated_at=state.updated_at,
                ))

        # Include persisted sessions not in memory
        if self._persist_sessions and self._session_dir.exists():
            for session_dir in self._session_dir.iterdir():
                if session_dir.is_dir():
                    sid = session_dir.name
                    if sid not in self._sessions:
                        state_file = session_dir / "acp_state.json"
                        if state_file.exists():
                            try:
                                data = json.loads(state_file.read_text(encoding="utf8"))
                                if cwd is None or data.get("cwd") == cwd:
                                    sessions.append(SessionInfo(
                                        session_id=sid,
                                        cwd=data.get("cwd", ""),
                                        title=data.get("title"),
                                        updated_at=data.get("updated_at"),
                                    ))
                            except (json.JSONDecodeError, OSError):
                                pass

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at or "", reverse=True)

        return ListSessionsResponse(sessions=sessions, next_cursor=None)

    async def fork_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> ForkSessionResponse:
        """Fork an existing session to create a new independent copy."""
        # Get source session
        source = self._sessions.get(session_id)
        if source is None and self._persist_sessions:
            source = self._load_session(session_id)

        # Create new session ID
        new_session_id = generate_session_id()

        if source:
            # Deep copy the state
            new_state = SessionState(
                prompt_history=copy.deepcopy(source.prompt_history),
                last_response_id=source.last_response_id,
                model_id=source.model_id,
                mode_id=source.mode_id or DEFAULT_MODE_ID,
                cwd=cwd,  # Use new cwd
                title=f"Fork of {source.title or session_id}",
                updated_at=_utc_now_iso(),
                config=copy.deepcopy(source.config),
            )
        else:
            # Create fresh session if source not found
            new_state = SessionState(mode_id=DEFAULT_MODE_ID, cwd=cwd, updated_at=_utc_now_iso())

        self._sessions[new_session_id] = new_state
        if self._persist_sessions:
            self._save_session(new_session_id, new_state)

        return ForkSessionResponse(
            session_id=new_session_id,
            modes=_build_mode_state(new_state.mode_id or DEFAULT_MODE_ID),
        )

    async def resume_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        """Resume a previously saved session."""
        # Try to load from disk
        if self._persist_sessions and session_id not in self._sessions:
            loaded = self._load_session(session_id)
            if loaded:
                loaded.cwd = cwd  # Update cwd
                loaded.updated_at = _utc_now_iso()
                self._sessions[session_id] = loaded

        # Create new if not found
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(mode_id=DEFAULT_MODE_ID, cwd=cwd, updated_at=_utc_now_iso())

        state = self._sessions[session_id]
        return ResumeSessionResponse(
            modes=_build_mode_state(state.mode_id or DEFAULT_MODE_ID),
        )

    async def set_session_mode(self, mode_id: str, session_id: str, **kwargs: Any) -> SetSessionModeResponse | None:
        state = self._sessions.setdefault(session_id, SessionState())
        # Validate mode_id
        valid_modes = {m["id"] for m in STEWARD_MODES}
        if mode_id not in valid_modes:
            # Return None or could raise - for now accept any mode
            pass
        state.mode_id = mode_id
        state.updated_at = _utc_now_iso()
        if self._persist_sessions:
            self._save_session(session_id, state)
        return SetSessionModeResponse()

    async def set_session_model(self, model_id: str, session_id: str, **kwargs: Any) -> SetSessionModelResponse | None:
        state = self._sessions.setdefault(session_id, SessionState())
        state.model_id = model_id
        state.updated_at = _utc_now_iso()
        if self._persist_sessions:
            self._save_session(session_id, state)
        return SetSessionModelResponse()

    def configure_session(
        self,
        session_id: str,
        *,
        system_prompt: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        max_steps: Optional[int] = None,
        timeout_ms: Optional[int] = None,
        retries: Optional[int] = None,
        require_permission: Optional[bool] = None,
    ) -> bool:
        """Configure session options (parity with REPL).

        This is a programmatic API for configuring sessions. ACP clients
        can call this via extension methods if needed.

        Returns True if session exists and was configured.
        """
        state = self._sessions.get(session_id)
        if state is None:
            return False

        if system_prompt is not None:
            state.config.system_prompt = system_prompt
        if custom_instructions is not None:
            state.config.custom_instructions = custom_instructions
        if max_steps is not None:
            state.config.max_steps = max_steps
        if timeout_ms is not None:
            state.config.timeout_ms = timeout_ms
        if retries is not None:
            state.config.retries = retries
        if require_permission is not None:
            state.config.require_permission = require_permission

        state.updated_at = _utc_now_iso()
        if self._persist_sessions:
            self._save_session(session_id, state)

        return True

    # Session persistence helpers

    def _save_session(self, session_id: str, state: SessionState) -> None:
        """Save session state to disk."""
        session_dir = self._session_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        state_file = session_dir / "acp_state.json"

        # Serialize state (exclude runtime-only fields)
        mcp_servers_data = [asdict(s) for s in state.mcp_servers] if state.mcp_servers else []
        data = {
            "prompt_history": state.prompt_history,
            "last_response_id": state.last_response_id,
            "model_id": state.model_id,
            "mode_id": state.mode_id,
            "cwd": state.cwd,
            "title": state.title,
            "updated_at": state.updated_at,
            "config": asdict(state.config),
            "mcp_servers": mcp_servers_data,
        }
        state_file.write_text(json.dumps(data, indent=2), encoding="utf8")

    def _load_session(self, session_id: str) -> Optional[SessionState]:
        """Load session state from disk."""
        state_file = self._session_dir / session_id / "acp_state.json"
        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text(encoding="utf8"))
            config_data = data.get("config", {})
            mcp_servers_data = data.get("mcp_servers", [])
            mcp_servers = [
                McpServerSpec(
                    name=s.get("name", ""),
                    server_type=s.get("server_type", "stdio"),
                    command=s.get("command"),
                    args=s.get("args", []),
                    env=s.get("env", {}),
                    url=s.get("url"),
                )
                for s in mcp_servers_data
            ]
            return SessionState(
                prompt_history=data.get("prompt_history", []),
                last_response_id=data.get("last_response_id"),
                model_id=data.get("model_id"),
                mode_id=data.get("mode_id"),
                cwd=data.get("cwd", ""),
                title=data.get("title"),
                updated_at=data.get("updated_at"),
                config=SessionConfig(
                    system_prompt=config_data.get("system_prompt"),
                    custom_instructions=config_data.get("custom_instructions"),
                    max_steps=config_data.get("max_steps"),
                    timeout_ms=config_data.get("timeout_ms"),
                    retries=config_data.get("retries"),
                    require_permission=config_data.get("require_permission", False),
                ),
                mcp_servers=mcp_servers,
            )
        except (json.JSONDecodeError, OSError):
            return None

    async def prompt(
        self,
        prompt: list[
            TextContentBlock
            | ImageContentBlock
            | AudioContentBlock
            | ResourceContentBlock
            | EmbeddedResourceContentBlock
        ],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        state = self._sessions.setdefault(session_id, SessionState())
        prompt_text = _prompt_to_text(prompt)

        # Apply plan mode prefix if in plan mode
        if state.mode_id == "plan":
            prompt_text = f"{PLAN_MODE_PREFIX} {prompt_text}"

        # Create event queue and cancellation token for this prompt
        event_queue = AcpEventQueue(session_id)
        cancellation_token = CancellationToken()
        state.event_queue = event_queue
        state.cancellation_token = cancellation_token

        # Build runner options from session state and config
        config = state.config
        options = RunnerOptions(
            prompt=prompt_text,
            provider=detect_provider(),
            model=state.model_id or DEFAULT_MODEL,
            system_prompt=config.system_prompt,
            custom_instructions=config.custom_instructions,
            max_steps=config.max_steps or DEFAULT_MAX_STEPS,
            request_timeout_ms=config.timeout_ms,
            retries=config.retries,
            conversation_history=state.prompt_history or None,
            previous_response_id=state.last_response_id,
            enable_human_logs=False,  # Use ACP streaming instead
            event_queue=event_queue,
            cancellation_token=cancellation_token,
            require_permission=config.require_permission,
        )

        # Start event dispatcher task
        dispatcher_task = asyncio.create_task(
            self._dispatch_events(session_id, event_queue)
        )

        # Run steward
        try:
            result = await run_steward_async(options)

            if result.messages:
                state.prompt_history = result.messages
            state.last_response_id = result.last_response_id
            state.updated_at = _utc_now_iso()

            # Persist session state
            if self._persist_sessions:
                self._save_session(session_id, state)

            # Send final response if not already streamed
            response_text = result.response or ""
            if response_text:
                await self._conn.session_update(
                    session_id=session_id,
                    update=update_agent_message(text_block(response_text)),
                )

            await self._send_usage_summary(session_id, result.usage_summary)

            stop_reason = "end_turn"
        except asyncio.CancelledError:
            stop_reason = "cancelled"
        finally:
            # Close event queue and wait for dispatcher to finish
            event_queue.close()
            await dispatcher_task
            state.event_queue = None
            state.cancellation_token = None

        return PromptResponse(stop_reason=stop_reason)

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Cancel the current operation for a session."""
        state = self._sessions.get(session_id)
        if state and state.cancellation_token:
            state.cancellation_token.cancel()
            if state.event_queue:
                state.event_queue.cancel()

    # --- Client-delegated file operations ---

    def supports_delegated_read(self) -> bool:
        """Check if client supports delegated file reads."""
        return self._client_fs.read_text_file

    def supports_delegated_write(self) -> bool:
        """Check if client supports delegated file writes."""
        return self._client_fs.write_text_file

    async def read_file_delegated(
        self, session_id: str, path: str, limit: int | None = None, line: int | None = None
    ) -> str | None:
        """Read a file via the ACP client (if supported).

        Returns file content if client supports delegation, None otherwise.
        """
        if not self._client_fs.read_text_file:
            return None
        try:
            response = await self._conn.read_text_file(
                path=path,
                session_id=session_id,
                limit=limit,
                line=line,
            )
            return response.content
        except Exception as err:
            self._logger.human(HumanEntry(title="acp", body=f"delegated read failed: {err}", variant="warn"))
            return None

    async def write_file_delegated(self, session_id: str, path: str, content: str) -> bool:
        """Write a file via the ACP client (if supported).

        Returns True if successfully delegated, False otherwise.
        """
        if not self._client_fs.write_text_file:
            return False
        try:
            await self._conn.write_text_file(
                path=path,
                session_id=session_id,
                content=content,
            )
            return True
        except Exception as err:
            self._logger.human(HumanEntry(title="acp", body=f"delegated write failed: {err}", variant="warn"))
            return False

    async def _dispatch_events(self, session_id: str, event_queue: AcpEventQueue) -> None:
        """Dispatch events from queue to ACP client."""
        while not event_queue.is_closed or not event_queue._queue.empty():
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                await self._send_event_to_client(session_id, event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as err:
                self._logger.human(HumanEntry(title="acp", body=f"event dispatch error: {err}", variant="warn"))

    async def _send_event_to_client(self, session_id: str, event: AcpEvent) -> None:
        """Convert AcpEvent to ACP protocol update and send to client."""
        if event.event_type == AcpEventType.TEXT_CHUNK:
            text = event.data.get("text", "")
            if text:
                await self._conn.session_update(
                    session_id=session_id,
                    update=update_agent_message(text_block(text)),
                )

        elif event.event_type == AcpEventType.TOOL_START:
            tool_name = event.data.get("tool_name", "") if not hasattr(event, "tool_name") else event.tool_name  # type: ignore
            tool_kind = event.data.get("tool_kind", "other") if not hasattr(event, "tool_kind") else event.tool_kind  # type: ignore
            await self._conn.session_update(
                session_id=session_id,
                update=start_tool_call(
                    tool_call_id=event.tool_call_id or "",
                    title=tool_name,
                    kind=tool_kind,
                    status="in_progress",
                ),
            )

        elif event.event_type in (AcpEventType.TOOL_COMPLETE, AcpEventType.TOOL_FAILED):
            tool_name = event.data.get("tool_name", "") if not hasattr(event, "tool_name") else event.tool_name  # type: ignore
            status = "completed" if event.event_type == AcpEventType.TOOL_COMPLETE else "failed"
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(
                    tool_call_id=event.tool_call_id or "",
                    title=tool_name,
                    status=status,
                ),
            )

        elif event.event_type == AcpEventType.TOOL_PROGRESS:
            tool_name = event.data.get("tool_name", "") if not hasattr(event, "tool_name") else event.tool_name  # type: ignore
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(
                    tool_call_id=event.tool_call_id or "",
                    title=tool_name,
                    status="in_progress",
                ),
            )

        elif event.event_type == AcpEventType.PERMISSION_REQUEST:
            # Permission requests need special handling - the client responds
            # via a separate mechanism. For now, auto-approve.
            # TODO: Implement proper permission flow with client
            request_id = event.data.get("request_id", "")
            if request_id:
                state = self._sessions.get(session_id)
                if state and state.event_queue:
                    state.event_queue.resolve_permission(
                        request_id,
                        PermissionResponse(request_id=request_id, approved=True, always_allow=False),
                    )

        elif event.event_type == AcpEventType.THOUGHT_CHUNK:
            # Stream agent thinking/reasoning to client
            text = event.data.get("text", "")
            if text:
                await self._conn.session_update(
                    session_id=session_id,
                    update=AgentThoughtChunk(
                        sessionUpdate="agent_thought_chunk",
                        content=text_block(text),
                    ),
                )

        elif event.event_type == AcpEventType.PLAN_UPDATE:
            # Send plan/TODO update to client
            entries_data = event.data.get("entries", [])
            if entries_data:
                entries = [
                    PlanEntry(
                        content=e.get("content", ""),
                        status=e.get("status", "pending"),
                        priority=e.get("priority", "medium"),
                    )
                    for e in entries_data
                ]
                await self._conn.session_update(
                    session_id=session_id,
                    update=AgentPlanUpdate(
                        sessionUpdate="plan",
                        entries=entries,
                    ),
                )

    async def _send_available_commands(self, session_id: str) -> None:
        """Send available REPL-like commands to ACP clients."""
        if not hasattr(self, "_conn"):
            return
        commands = [
            AvailableCommand(name="stats", description="Show token usage for the session"),
            AvailableCommand(name="history", description="Show recent REPL history"),
            AvailableCommand(name="new", description="Start a new conversation"),
            AvailableCommand(name="clear", description="Clear the display"),
        ]
        await self._conn.session_update(
            session_id=session_id,
            update=AvailableCommandsUpdate(
                sessionUpdate="available_commands_update",
                availableCommands=commands,
            ),
        )

    async def _send_usage_summary(self, session_id: str, usage: Optional[dict]) -> None:
        """Send usage summary as a session info update."""
        if not hasattr(self, "_conn"):
            return
        if not usage:
            return
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        cached = usage.get("cached_tokens", 0)
        cache_pct = int(100 * cached / prompt) if cached and prompt else 0
        title = f"tokens: prompt={prompt}, completion={completion}, total={total}"
        if cached:
            title += f", cached={cached} ({cache_pct}%)"
        await self._conn.session_update(
            session_id=session_id,
            update=SessionInfoUpdate(
                sessionUpdate="session_info_update",
                title=title,
                updatedAt=_utc_now_iso(),
            ),
        )

    def resolve_permission(self, session_id: str, request_id: str, approved: bool, always_allow: bool = False) -> bool:
        """Resolve a pending permission request from the client.

        This method should be called when the client responds to a permission request.
        Returns True if the request was found and resolved.
        """
        state = self._sessions.get(session_id)
        if state and state.event_queue:
            return state.event_queue.resolve_permission(
                request_id,
                PermissionResponse(request_id=request_id, approved=approved, always_allow=always_allow),
            )
        return False


def _build_mode_state(current_mode_id: str) -> SessionModeState:
    """Build SessionModeState with available modes."""
    return SessionModeState(
        available_modes=[
            SessionMode(id=m["id"], name=m["name"], description=m["description"])
            for m in STEWARD_MODES
        ],
        current_mode_id=current_mode_id,
    )


def _prompt_to_text(
    prompt: list[
        TextContentBlock | ImageContentBlock | AudioContentBlock | ResourceContentBlock | EmbeddedResourceContentBlock
    ],
) -> str:
    parts: List[str] = []
    for block in prompt:
        if isinstance(block, dict):
            text = block.get("text")
            resource = block.get("resource") if text is None else None
            if text is None and isinstance(resource, dict):
                text = resource.get("text")
        else:
            text = getattr(block, "text", None)
            if text is None:
                resource = getattr(block, "resource", None)
                text = getattr(resource, "text", None) if resource is not None else None
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _parse_mcp_servers(
    mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
) -> List[McpServerSpec]:
    """Parse ACP MCP server configs into internal format."""
    specs: List[McpServerSpec] = []
    for i, server in enumerate(mcp_servers):
        if isinstance(server, dict):
            # Handle dict format
            if "command" in server:
                # Stdio server
                specs.append(McpServerSpec(
                    name=server.get("name", f"mcp-{i}"),
                    server_type="stdio",
                    command=server.get("command"),
                    args=server.get("args", []),
                    env=server.get("env", {}),
                ))
            elif "url" in server:
                # HTTP or SSE server
                server_type = "sse" if "sse" in server.get("url", "").lower() else "http"
                specs.append(McpServerSpec(
                    name=server.get("name", f"mcp-{i}"),
                    server_type=server_type,
                    url=server.get("url"),
                ))
        elif hasattr(server, "command"):
            # McpServerStdio
            specs.append(McpServerSpec(
                name=getattr(server, "name", f"mcp-{i}"),
                server_type="stdio",
                command=getattr(server, "command", None),
                args=getattr(server, "args", []) or [],
                env=dict(getattr(server, "env", {}) or {}),
            ))
        elif hasattr(server, "url"):
            # HttpMcpServer or SseMcpServer
            url = getattr(server, "url", "")
            is_sse = isinstance(server, SseMcpServer) if hasattr(server, "__class__") else "sse" in url.lower()
            specs.append(McpServerSpec(
                name=getattr(server, "name", f"mcp-{i}"),
                server_type="sse" if is_sse else "http",
                url=url,
            ))
    return specs


def _utc_now_iso() -> str:
    """Return current UTC time in ISO format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    asyncio.run(run_agent(StewardAcpAgent()))


def _get_version() -> str:
    return get_version()
