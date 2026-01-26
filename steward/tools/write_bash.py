"""write_bash tool - send input to async bash sessions."""
from __future__ import annotations

from time import sleep
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .bash import get_session
from .shared import truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "write_bash",
    "description": "Send input to an async bash session. Supports text and special keys like {enter}, {up}, {down}.",
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {
                "type": "string",
                "description": "The session ID to write to.",
            },
            "input": {
                "type": "string",
                "description": "The input to send. Use {enter}, {up}, {down}, {left}, {right}, {backspace} for special keys.",
            },
            "delay": {
                "type": "number",
                "description": "Time in seconds to wait after sending input before reading output (default: 10).",
            },
        },
        "required": ["sessionId"],
    },
}

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


def tool_handler(args: Dict) -> ToolResult:
    session_id = args.get("sessionId")
    if not isinstance(session_id, str):
        raise ValueError("'sessionId' is required")

    input_text = args.get("input", "")
    delay = args.get("delay") if isinstance(args.get("delay"), (int, float)) else 10

    session = get_session(session_id)
    if not session:
        return {"id": "write_bash", "output": f"Session {session_id} not found"}

    proc = session["proc"]

    # Check if process already completed
    if proc.poll() is not None:
        return {"id": "write_bash", "output": f"Session {session_id} already completed (exit {proc.returncode})"}

    # Check if stdin is available
    if proc.stdin is None:
        return {"id": "write_bash", "output": f"Session {session_id} has no stdin available"}

    # Expand special keys and write
    expanded = _expand_special_keys(input_text)
    try:
        proc.stdin.write(expanded)
        proc.stdin.flush()
    except Exception as e:
        return {"id": "write_bash", "output": f"Failed to write to session: {e}"}

    # Wait and read output
    if delay > 0:
        sleep(min(delay, 300))

    output_parts = []
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(stderr)
        output = "\n".join(output_parts) if output_parts else "(no output)"
        return {"id": "write_bash", "output": f"[completed, exit code {proc.returncode}]\n{truncate_output(output, 32000)}"}

    output_parts.append(f"[still running, pid: {proc.pid}]")
    return {"id": "write_bash", "output": "\n".join(output_parts)}
