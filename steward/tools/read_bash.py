"""read_bash tool - read output from async bash sessions."""

from __future__ import annotations

from time import sleep
from typing import Optional

from ..types import ToolResult
from .bash import get_session
from .shared import truncate_output


def tool_read_bash(sessionId: str, delay: Optional[float] = None) -> ToolResult:
    """Read output from an async bash session.

    Args:
        sessionId: The session ID returned by bash with mode='async'
        delay: Time in seconds to wait before reading output (default: 5)
    """
    wait_time = delay if delay is not None else 5
    if wait_time > 0:
        sleep(min(wait_time, 300))  # Cap at 5 minutes

    session = get_session(sessionId)
    if not session:
        return {"id": "read_bash", "output": f"Session {sessionId} not found"}

    proc = session["proc"]
    output_parts = []

    # Check if process completed
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(stderr)
        output = "\n".join(output_parts) if output_parts else "(no output)"
        return {
            "id": "read_bash",
            "output": f"[completed, exit code {proc.returncode}]\n{truncate_output(output, 32000)}",
            "next_tool": ["stop_bash"],
        }

    # Process still running - read available output
    output_parts.append(f"[still running, pid: {proc.pid}]")

    # Try non-blocking read if available
    if hasattr(proc.stdout, "read1"):
        try:
            data = proc.stdout.read1(8192)
            if data:
                output_parts.append(data if isinstance(data, str) else data.decode("utf8", errors="ignore"))
        except Exception as err:
            return {
                "id": "read_bash",
                "output": f"[error reading output: {err}]",
                "error": True,
                "next_tool": ["stop_bash"],
            }

    return {"id": "read_bash", "output": "\n".join(output_parts), "next_tool": ["write_bash", "read_bash"]}
