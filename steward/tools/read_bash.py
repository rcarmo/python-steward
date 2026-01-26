"""read_bash tool - read output from async bash sessions."""
from __future__ import annotations

from time import sleep
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .bash import get_session
from .shared import truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "read_bash",
    "description": "Read output from an async bash session.",
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {
                "type": "string",
                "description": "The session ID returned by bash with mode='async'.",
            },
            "delay": {
                "type": "number",
                "description": "Time in seconds to wait before reading output (default: 5).",
            },
        },
        "required": ["sessionId"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    session_id = args.get("sessionId")
    if not isinstance(session_id, str):
        raise ValueError("'sessionId' is required")

    delay = args.get("delay") if isinstance(args.get("delay"), (int, float)) else 5
    if delay > 0:
        sleep(min(delay, 300))  # Cap at 5 minutes

    session = get_session(session_id)
    if not session:
        return {"id": "read_bash", "output": f"Session {session_id} not found"}

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
        return {"id": "read_bash", "output": f"[completed, exit code {proc.returncode}]\n{truncate_output(output, 32000)}"}

    # Process still running - read available output
    output_parts.append(f"[still running, pid: {proc.pid}]")

    # Try non-blocking read if available
    if hasattr(proc.stdout, "read1"):
        try:
            data = proc.stdout.read1(8192)
            if data:
                output_parts.append(data if isinstance(data, str) else data.decode("utf8", errors="ignore"))
        except Exception:
            pass

    return {"id": "read_bash", "output": "\n".join(output_parts)}
