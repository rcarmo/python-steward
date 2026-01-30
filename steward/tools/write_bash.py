"""write_bash tool - send input to async bash sessions."""

from __future__ import annotations

from time import sleep
from typing import Optional

from ..types import ToolResult
from .bash import get_session
from .shared import truncate_output

# Special key mappings
_SPECIAL_KEYS = {
    "{enter}": "\n",
    "{up}": "\x1b[A",
    "{down}": "\x1b[B",
    "{left}": "\x1b[D",
    "{right}": "\x1b[C",
    "{backspace}": "\x7f",
}


def _expand_special_keys(text: str) -> str:
    """Expand special key sequences in input."""
    result = text
    for key, code in _SPECIAL_KEYS.items():
        result = result.replace(key, code)
    return result


def tool_write_bash(sessionId: str, input: Optional[str] = None, delay: Optional[float] = None) -> ToolResult:
    """Send input to an async bash session. Supports text and special keys.

    Args:
        sessionId: The session ID to write to
        input: The input to send, use {enter}, {up}, {down} for special keys
        delay: Time in seconds to wait after sending input (default: 10)
    """
    input_text = input if input is not None else ""
    wait_time = delay if delay is not None else 10

    session = get_session(sessionId)
    if not session:
        return {"id": "write_bash", "output": f"Session {sessionId} not found"}

    proc = session["proc"]

    # Check if process already completed
    if proc.poll() is not None:
        return {"id": "write_bash", "output": f"Session {sessionId} already completed (exit {proc.returncode})"}

    # Check if stdin is available
    if proc.stdin is None:
        return {"id": "write_bash", "output": f"Session {sessionId} has no stdin available"}

    # Expand special keys and write
    expanded = _expand_special_keys(input_text)
    try:
        proc.stdin.write(expanded)
        proc.stdin.flush()
    except Exception as e:
        return {"id": "write_bash", "output": f"Failed to write to session: {e}"}

    # Wait and read output
    if wait_time > 0:
        sleep(min(wait_time, 300))

    output_parts = []
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(stderr)
        output = "\n".join(output_parts) if output_parts else "(no output)"
        return {
            "id": "write_bash",
            "output": f"[completed, exit code {proc.returncode}]\n{truncate_output(output, 32000)}",
            "next_tool": ["stop_bash"],
        }

    output_parts.append(f"[still running, pid: {proc.pid}]")
    return {"id": "write_bash", "output": "\n".join(output_parts), "next_tool": ["read_bash", "write_bash"]}
