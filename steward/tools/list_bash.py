"""list_bash tool - list active bash sessions."""

from __future__ import annotations

from ..types import ToolResult
from .bash import list_sessions


def tool_list_bash() -> ToolResult:
    """List all active async bash sessions."""
    sessions = list_sessions()

    if not sessions:
        return {"id": "list_bash", "output": "No active sessions", "next_tool": ["bash"]}

    lines = []
    for sid, info in sessions.items():
        proc = info["proc"]
        status = "running" if proc.poll() is None else f"completed (exit {proc.returncode})"
        lines.append(f"- {sid}: {status}, cmd: {info['command'][:50]}..., started: {info['started']}")

    return {"id": "list_bash", "output": "\n".join(lines), "next_tool": ["read_bash", "stop_bash"]}
