"""ACP server for Steward."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
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
    text_block,
    update_agent_message,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AudioContentBlock,
    ClientCapabilities,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    McpServerStdio,
    ResourceContentBlock,
    SseMcpServer,
    TextContentBlock,
)

from .config import DEFAULT_MODEL, detect_provider
from .runner import RunnerOptions, run_steward_with_history
from .session import generate_session_id


@dataclass
class SessionState:
    prompt_history: List[Dict[str, Any]] = field(default_factory=list)
    last_response_id: Optional[str] = None
    model_id: Optional[str] = None
    mode_id: Optional[str] = None


class StewardAcpAgent(Agent):
    _conn: Client

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}

    def on_connect(self, conn: Client) -> None:
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(load_session=True),
            agent_info=Implementation(name="steward", title="Steward", version=_get_version()),
        )

    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        return AuthenticateResponse()

    async def new_session(
        self, cwd: str, mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio], **kwargs: Any
    ) -> NewSessionResponse:
        session_id = generate_session_id()
        self._sessions[session_id] = SessionState()
        return NewSessionResponse(session_id=session_id, modes=None)

    async def load_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
        session_id: str,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        self._sessions.setdefault(session_id, SessionState())
        return LoadSessionResponse()

    async def set_session_mode(self, mode_id: str, session_id: str, **kwargs: Any) -> SetSessionModeResponse | None:
        state = self._sessions.setdefault(session_id, SessionState())
        state.mode_id = mode_id
        return SetSessionModeResponse()

    async def set_session_model(self, model_id: str, session_id: str, **kwargs: Any) -> SetSessionModelResponse | None:
        state = self._sessions.setdefault(session_id, SessionState())
        state.model_id = model_id
        return SetSessionModelResponse()

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
        options = RunnerOptions(
            prompt=prompt_text,
            provider=detect_provider(),
            model=state.model_id or DEFAULT_MODEL,
            conversation_history=state.prompt_history or None,
            previous_response_id=state.last_response_id,
        )
        result = await asyncio.to_thread(run_steward_with_history, options)
        if result.messages:
            state.prompt_history = result.messages
        state.last_response_id = result.last_response_id
        response_text = result.response or ""
        await self._conn.session_update(session_id=session_id, update=update_agent_message(text_block(response_text)))
        return PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        return None


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


def main() -> None:
    asyncio.run(run_agent(StewardAcpAgent()))


def _get_version() -> str:
    try:
        return pkg_version("steward")
    except PackageNotFoundError:
        return "0.0.0"
