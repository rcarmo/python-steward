"""list_bash tool - list active bash sessions."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult
from .bash import list_sessions

TOOL_DEFINITION: ToolDefinition = {
    "name": "list_bash",
    "description": "List all active async bash sessions.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


def tool_handler(args: Dict) -> ToolResult:
    sessions = list_sessions()

    if not sessions:
        return {"id": "list_bash", "output": "No active sessions"}

    lines = []
    for sid, info in sessions.items():
        proc = info["proc"]
        status = "running" if proc.poll() is None else f"completed (exit {proc.returncode})"
        lines.append(f"- {sid}: {status}, cmd: {info['command'][:50]}..., started: {info['started']}")

    return {"id": "list_bash", "output": "\n".join(lines)}
