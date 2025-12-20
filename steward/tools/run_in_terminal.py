"""run_in_terminal tool (per-call shell execution)."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..config import env_list
from ..types import ToolDefinition, ToolResult
from .shared import audit_execute, env_cap, ensure_inside_workspace, normalize_path, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "run_in_terminal",
    "description": "Run a shell command with optional args (non-persistent session)",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
            "cwd": {"type": "string"},
            "env": {"type": "object"},
            "timeoutMs": {"type": "number"},
            "background": {"type": "boolean"},
            "stream": {"type": "boolean"},
            "maxOutputBytes": {"type": "number"},
        },
        "required": ["command"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    if not isinstance(args.get("command"), str):
        raise ValueError("'command' must be a string")
    if environ_get("STEWARD_ALLOW_EXECUTE") != "1":
        raise ValueError("run_in_terminal disabled; set STEWARD_ALLOW_EXECUTE=1 to enable")

    command = args["command"]
    arg_list: List[str] = [item for item in args.get("args", []) if isinstance(item, str)]
    cwd = normalize_path(args.get("cwd")) if isinstance(args.get("cwd"), str) else Path.cwd()
    env_args = args.get("env") if isinstance(args.get("env"), dict) else None
    timeout_ms = args.get("timeoutMs") if isinstance(args.get("timeoutMs"), int) else None
    background = args.get("background") is True
    stream = args.get("stream") is True
    max_output_bytes = args.get("maxOutputBytes") if isinstance(args.get("maxOutputBytes"), int) else env_cap(
        "STEWARD_EXEC_MAX_OUTPUT_BYTES", 32000
    )
    env_allow = env_list("STEWARD_EXEC_ALLOW")
    env_deny = env_list("STEWARD_EXEC_DENY")
    env_timeout_ms = environ_int("STEWARD_EXEC_TIMEOUT_MS")
    effective_timeout = timeout_ms if timeout_ms is not None else env_timeout_ms
    audit_enabled = environ_get("STEWARD_EXEC_AUDIT") != "0"

    if env_allow and command not in env_allow:
        raise ValueError("command not allowed by STEWARD_EXEC_ALLOW")
    if env_deny and command in env_deny:
        raise ValueError("command blocked by STEWARD_EXEC_DENY")

    ensure_inside_workspace(cwd)

    env = None
    if env_args:
        env = {k: str(v) for k, v in env_args.items() if isinstance(k, str) and isinstance(v, str)}

    if background:
        proc = subprocess.Popen([command, *arg_list], cwd=str(cwd), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if audit_enabled:
            audit_execute({
                "ts": _utc_now_iso(),
                "command": command,
                "args": arg_list,
                "cwd": str(cwd),
                "exitCode": None,
                "mode": "background",
            })
        return {"id": "run_in_terminal", "output": f"started pid {proc.pid}"}

    if stream:
        proc = subprocess.Popen([command, *arg_list], cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate(timeout=_timeout_sec(effective_timeout) if effective_timeout else None)
        combined = f"{stdout}{stderr}" if stderr else stdout
        truncated = truncate_output(combined, max_output_bytes)
        if audit_enabled:
            audit_execute({
                "ts": _utc_now_iso(),
                "command": command,
                "args": arg_list,
                "cwd": str(cwd),
                "exitCode": proc.returncode,
                "mode": "stream",
                "truncated": truncated.endswith("[truncated]"),
            })
        return {"id": "run_in_terminal", "output": truncated}

    try:
        completed = subprocess.run(
            [command, *arg_list],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=_timeout_sec(effective_timeout) if effective_timeout else None,
        )
        body = f"exit {completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        truncated = truncate_output(body, max_output_bytes)
        if audit_enabled:
            audit_execute({
                "ts": _utc_now_iso(),
                "command": command,
                "args": arg_list,
                "cwd": str(cwd),
                "exitCode": completed.returncode,
                "mode": "default",
                "truncated": truncated.endswith("[truncated]"),
            })
        return {"id": "run_in_terminal", "output": truncated}
    except subprocess.TimeoutExpired:
        body = "error: Timed out"
        if audit_enabled:
            audit_execute({
                "ts": _utc_now_iso(),
                "command": command,
                "args": arg_list,
                "cwd": str(cwd),
                "exitCode": None,
                "mode": "error",
                "error": "timeout",
            })
        return {"id": "run_in_terminal", "output": body, "error": True}


def environ_get(name: str) -> Optional[str]:
    from os import getenv

    return getenv(name)


def environ_int(name: str) -> Optional[int]:
    raw = environ_get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _timeout_sec(timeout_ms: Optional[int]) -> Optional[float]:
    if timeout_ms is None:
        return None
    return timeout_ms / 1000.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
