"""run_js tool using quickjs."""
from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import List, Optional

import quickjs

from ..types import ToolResult
from .shared import ensure_inside_workspace, env_cap, normalize_path, truncate_output

JS_DEFAULT_TIMEOUT_MS = env_cap("STEWARD_JS_TIMEOUT_MS", 2000)
JS_MAX_OUTPUT_BYTES = env_cap("STEWARD_JS_MAX_OUTPUT_BYTES", 16000)


def tool_run_js(
    code: Optional[str] = None,
    path: Optional[str] = None,
    timeoutMs: Optional[int] = None,
    maxOutputBytes: Optional[int] = None,
    sandboxDir: str = "/sandbox",
    allowNetwork: bool = False,
) -> ToolResult:
    """Execute JavaScript in a sandboxed QuickJS runtime.

    Args:
        code: JavaScript code to execute (provide this OR path)
        path: Path to JavaScript file to execute (provide this OR code)
        timeoutMs: Execution timeout in milliseconds (default: 2000)
        maxOutputBytes: Maximum output size in bytes (default: 16000)
        sandboxDir: Directory to use as sandbox root (default: /sandbox)
        allowNetwork: If true, allow network access
    """
    js_code = code
    if js_code is None and path:
        abs_path = normalize_path(path)
        ensure_inside_workspace(abs_path)
        js_code = Path(abs_path).read_text(encoding="utf8")
    if js_code is None:
        raise ValueError("Either 'code' or 'path' must be provided")

    timeout_ms = timeoutMs if timeoutMs is not None else JS_DEFAULT_TIMEOUT_MS
    max_output = maxOutputBytes if maxOutputBytes is not None else JS_MAX_OUTPUT_BYTES

    parent_conn, child_conn = mp.Pipe()
    proc = mp.Process(target=_run_js_worker, args=(child_conn, js_code, allowNetwork, sandboxDir))
    proc.start()
    proc.join(timeout_ms / 1000.0)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        status, result_text, logs = "timeout", "Timed out", []
    else:
        if parent_conn.poll():
            status, result_text, logs = parent_conn.recv()
        else:
            status, result_text, logs = "error", "No result", []

    parts = [f"status: {status}", f"result: {result_text}"]
    if logs:
        parts.append("console:")
        parts.extend(logs)
    output = truncate_output("\n".join(parts), max_output)
    return {"id": "run_js", "output": output, "error": status != "ok"}


def _render(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _run_js_worker(conn, code: str, allow_network: bool, sandbox_root: str) -> None:
    logs: List[str] = []

    def _log(prefix: str, *values) -> None:
        rendered = " ".join([str(v) for v in values])
        logs.append(f"{prefix}: {rendered}" if rendered else prefix)

    ctx = quickjs.Context()
    ctx.add_callable("__console_log", lambda *values: _log("log", *values))
    ctx.add_callable("__console_warn", lambda *values: _log("warn", *values))
    ctx.add_callable("__console_error", lambda *values: _log("error", *values))
    ctx.eval("const console={log:(...a)=>__console_log(...a),warn:(...a)=>__console_warn(...a),error:(...a)=>__console_error(...a)};")
    ctx.eval(f"const SANDBOX_ROOT='{sandbox_root}';")

    if allow_network:
        _install_fetch(ctx)

    status = "ok"
    result_text = "undefined"
    try:
        result = ctx.eval(code)
        result_text = _render(result)
    except quickjs.JSException as exc:  # noqa: PERF203
        status = "error"
        result_text = str(exc)
    conn.send((status, result_text, logs))
    conn.close()


def _install_fetch(ctx: quickjs.Context) -> None:
    import requests

    def _fetch(url: str) -> str:
        resp = requests.get(url, timeout=5)
        return resp.text

    ctx.add_callable("__py_fetch", _fetch)
    ctx.eval("async function fetch(u){ return __py_fetch(u); }")
