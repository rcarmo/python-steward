"""stop_bash tool - stop an async bash session."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult
from .bash import stop_session

TOOL_DEFINITION: ToolDefinition = {
    "name": "stop_bash",
    "description": "Stop a running async bash session by terminating the process.",
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {
                "type": "string",
                "description": "The session ID to stop.",
            },
        },
        "required": ["sessionId"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    session_id = args.get("sessionId")
    if not isinstance(session_id, str):
        raise ValueError("'sessionId' is required")

    result = stop_session(session_id)
    return {"id": "stop_bash", "output": result}
