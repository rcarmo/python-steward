"""stop_bash tool - stop an async bash session."""
from __future__ import annotations

from ..types import ToolResult
from .bash import stop_session


def tool_stop_bash(sessionId: str) -> ToolResult:
    """Stop a running async bash session by terminating the process.

    Args:
        sessionId: The session ID to stop
    """
    result = stop_session(sessionId)
    return {"id": "stop_bash", "output": result}
