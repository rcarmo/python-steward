"""bash tool - shell execution (aligned with Copilot CLI)."""

from __future__ import annotations

import subprocess
import threading
import uuid
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from typing import Dict, Optional

from ..config import env_list
from ..types import ToolResult
from .shared import audit_execute, ensure_inside_workspace, env_cap, normalize_path, truncate_output

# Session storage for async processes
_sessions: Dict[str, dict] = {}
_sessions_lock = threading.Lock()


def tool_bash(
    command: str,
    description: str = "",
    mode: str = "sync",
    initial_wait: Optional[float] = None,
    detach: bool = False,
    cwd: Optional[str] = None,
) -> ToolResult:
    """Run a shell command.

    Args:
        command: The bash command to run
        description: Short description for logging
        mode: 'sync' (default) or 'async'
        initial_wait: Seconds to wait for output in sync mode (default: 30)
        detach: If true with async, process persists after session
        cwd: Working directory for the command
    """
    if getenv("STEWARD_ALLOW_EXECUTE") != "1":
        raise ValueError("bash disabled; set STEWARD_ALLOW_EXECUTE=1 to enable")

    wait_time = initial_wait if initial_wait is not None else 30
    working_dir = normalize_path(cwd) if cwd else Path.cwd()

    ensure_inside_workspace(working_dir)

    # Check allow/deny lists
    env_allow = env_list("STEWARD_EXEC_ALLOW")
    env_deny = env_list("STEWARD_EXEC_DENY")
    cmd_name = command.split()[0] if command.split() else command

    if env_allow and cmd_name not in env_allow:
        raise ValueError(f"command '{cmd_name}' not allowed by STEWARD_EXEC_ALLOW")
    if env_deny and cmd_name in env_deny:
        raise ValueError(f"command '{cmd_name}' blocked by STEWARD_EXEC_DENY")

    max_output_bytes = env_cap("STEWARD_EXEC_MAX_OUTPUT_BYTES", 32000)
    audit_enabled = getenv("STEWARD_EXEC_AUDIT") != "0"

    if mode == "async":
        return _run_async(command, working_dir, detach, audit_enabled, description)
    else:
        return _run_sync(command, working_dir, wait_time, max_output_bytes, audit_enabled, description)


def _run_sync(
    command: str, cwd: Path, initial_wait: float, max_output_bytes: int, audit_enabled: bool, description: str
) -> ToolResult:
    """Run command synchronously, waiting up to initial_wait seconds."""
    session_id = str(uuid.uuid4())[:8]

    try:
        completed = subprocess.run(
            ["bash", "-c", command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=initial_wait,
        )
        output = completed.stdout
        if completed.stderr:
            output += f"\n{completed.stderr}" if output else completed.stderr

        if completed.returncode != 0:
            output = f"exit code {completed.returncode}\n{output}"

        truncated = truncate_output(output, max_output_bytes)

        if audit_enabled:
            audit_execute(
                {
                    "ts": _utc_now_iso(),
                    "command": command,
                    "cwd": str(cwd),
                    "exitCode": completed.returncode,
                    "mode": "sync",
                    "description": description,
                }
            )

        return {"id": "bash", "output": truncated}

    except subprocess.TimeoutExpired as e:
        # Command still running, return partial output
        partial_output = ""
        if e.stdout:
            partial_output = e.stdout.decode("utf8", errors="ignore") if isinstance(e.stdout, bytes) else e.stdout
        if e.stderr:
            err = e.stderr.decode("utf8", errors="ignore") if isinstance(e.stderr, bytes) else e.stderr
            partial_output += f"\n{err}" if partial_output else err

        truncated = truncate_output(partial_output, max_output_bytes)
        output = f"[still running after {initial_wait}s, sessionId: {session_id}]\n{truncated}"

        if audit_enabled:
            audit_execute(
                {
                    "ts": _utc_now_iso(),
                    "command": command,
                    "cwd": str(cwd),
                    "exitCode": None,
                    "mode": "sync-partial",
                    "description": description,
                }
            )

        return {"id": "bash", "output": output, "next_tool": ["view", "grep"]}


def _run_async(command: str, cwd: Path, detach: bool, audit_enabled: bool, description: str) -> ToolResult:
    """Run command asynchronously in background."""
    session_id = str(uuid.uuid4())[:8]

    if detach:
        # Fully detached process that survives session end
        proc = subprocess.Popen(
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if audit_enabled:
            audit_execute(
                {
                    "ts": _utc_now_iso(),
                    "command": command,
                    "cwd": str(cwd),
                    "exitCode": None,
                    "mode": "async-detached",
                    "pid": proc.pid,
                    "description": description,
                }
            )
        return {
            "id": "bash",
            "output": f"Started detached process (pid: {proc.pid}, sessionId: {session_id})",
            "next_tool": ["list_bash"],
        }
    else:
        # Async but attached - can read/write later
        proc = subprocess.Popen(
            ["bash", "-c", command],
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with _sessions_lock:
            _sessions[session_id] = {
                "proc": proc,
                "command": command,
                "cwd": str(cwd),
                "started": _utc_now_iso(),
            }

        if audit_enabled:
            audit_execute(
                {
                    "ts": _utc_now_iso(),
                    "command": command,
                    "cwd": str(cwd),
                    "exitCode": None,
                    "mode": "async",
                    "sessionId": session_id,
                    "pid": proc.pid,
                    "description": description,
                }
            )

        return {
            "id": "bash",
            "output": f"Started async process (pid: {proc.pid}, sessionId: {session_id})",
            "next_tool": ["read_bash", "write_bash"],
        }


def get_session(session_id: str) -> Optional[dict]:
    """Get session info by ID."""
    with _sessions_lock:
        return _sessions.get(session_id)


def list_sessions() -> Dict[str, dict]:
    """List all active sessions."""
    with _sessions_lock:
        return dict(_sessions)


def read_session_output(session_id: str, timeout: float = 5.0) -> str:
    """Read output from an async session."""
    session = get_session(session_id)
    if not session:
        return f"Session {session_id} not found"

    proc = session["proc"]
    if proc.poll() is not None:
        # Process finished
        stdout, stderr = proc.communicate()
        output = stdout
        if stderr:
            output += f"\n{stderr}" if output else stderr
        return f"[completed, exit code {proc.returncode}]\n{output}"

    # Process still running - try to read available output
    return f"[still running, pid: {proc.pid}]"


def stop_session(session_id: str) -> str:
    """Stop an async session."""
    with _sessions_lock:
        session = _sessions.pop(session_id, None)

    if not session:
        return f"Session {session_id} not found"

    proc = session["proc"]
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return f"Session {session_id} terminated"
    else:
        return f"Session {session_id} already completed"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
