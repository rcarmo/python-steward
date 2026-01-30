"""run_js tool using quickjs."""

from __future__ import annotations

import json
import multiprocessing as mp
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import quickjs

from ..types import ToolResult
from .shared import ensure_inside_workspace, env_cap, normalize_path, truncate_output

JS_DEFAULT_TIMEOUT_MS = env_cap("STEWARD_JS_TIMEOUT_MS", 2000)
JS_MAX_OUTPUT_BYTES = env_cap("STEWARD_JS_MAX_OUTPUT_BYTES", 16000)
JS_FUNCTION_NAME = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")
JS_RESULT_FORMATS = {"json", "text"}

JS_CALL_HELPERS = """
function __steward_get(path) {
  return (0, eval)(path);
}
function __steward_call(path, params) {
  const fn = __steward_get(path);
  if (typeof fn !== "function") {
    throw new Error("Function not found: " + path);
  }
  return fn(params);
}
function __steward_run_calls(calls, asJson) {
  if (!Array.isArray(calls)) {
    throw new Error("Calls must be an array");
  }
  const results = calls.map((call) => __steward_call(call.function, call.params || {}));
  if (asJson) {
    return JSON.stringify(results.length === 1 ? results[0] : results);
  }
  if (results.length === 1) {
    return String(results[0]);
  }
  return results.map((item) => String(item)).join("\\n");
}
"""


def _validate_function_name(name: str) -> None:
    if not JS_FUNCTION_NAME.fullmatch(name):
        raise ValueError(f"Invalid function name: {name}")


def _normalize_calls(
    function: Optional[str],
    params: Optional[Dict[str, Any]],
    calls: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    if function and calls:
        raise ValueError("Provide either 'function' or 'calls', not both")
    if function:
        _validate_function_name(function)
        return [{"function": function, "params": params or {}}]
    if not calls:
        return None
    normalized: List[Dict[str, Any]] = []
    for call in calls:
        if not isinstance(call, dict):
            raise ValueError("Each call must be an object")
        function_name = call.get("function")
        if not function_name:
            raise ValueError("Each call must include 'function'")
        if not isinstance(function_name, str):
            raise ValueError("Call 'function' must be a string")
        _validate_function_name(function_name)
        call_params = call.get("params")
        if call_params is None:
            call_params = {}
        if not isinstance(call_params, dict):
            raise ValueError("Call 'params' must be an object")
        normalized.append({"function": function_name, "params": call_params})
    return normalized


def _resolve_result_format(result_format: Optional[str], has_calls: bool) -> str:
    if result_format is None:
        return "json" if has_calls else "text"
    if result_format not in JS_RESULT_FORMATS:
        raise ValueError("resultFormat must be 'json' or 'text'")
    return result_format


def _serialize_calls(calls: List[Dict[str, Any]]) -> str:
    try:
        return json.dumps(calls)
    except TypeError as exc:
        raise ValueError("Call parameters must be JSON-serializable") from exc


def tool_run_js(
    code: Optional[str] = None,
    path: Optional[str] = None,
    function: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    calls: Optional[List[Dict[str, Any]]] = None,
    resultFormat: Optional[str] = None,
    timeoutMs: Optional[int] = None,
    maxOutputBytes: Optional[int] = None,
    sandboxDir: str = "/sandbox",
    allowNetwork: bool = False,
) -> ToolResult:
    """Execute JavaScript in a sandboxed QuickJS runtime.

    Args:
        code: JavaScript code to execute (provide this OR path)
        path: Path to JavaScript file to execute (provide this OR code)
        function: Name of a function to call after loading code/path
        params: Named parameters to pass to function
        calls: List of {"function": str, "params": {}} call objects to execute in order
        resultFormat: "json" or "text" (default: json for calls, text otherwise)
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
    normalized_calls = _normalize_calls(function, params, calls)
    result_format = _resolve_result_format(resultFormat, normalized_calls is not None)
    calls_json = _serialize_calls(normalized_calls) if normalized_calls else None

    parent_conn, child_conn = mp.Pipe()
    proc = mp.Process(
        target=_run_js_worker,
        args=(child_conn, js_code, allowNetwork, sandboxDir, calls_json, result_format),
    )
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


def _run_js_worker(
    conn,
    code: str,
    allow_network: bool,
    sandbox_root: str,
    calls_json: Optional[str],
    result_format: str,
) -> None:
    logs: List[str] = []

    def _log(prefix: str, *values) -> None:
        rendered = " ".join([str(v) for v in values])
        logs.append(f"{prefix}: {rendered}" if rendered else prefix)

    ctx = quickjs.Context()
    ctx.add_callable("__console_log", lambda *values: _log("log", *values))
    ctx.add_callable("__console_warn", lambda *values: _log("warn", *values))
    ctx.add_callable("__console_error", lambda *values: _log("error", *values))
    ctx.eval(
        "const console={log:(...a)=>__console_log(...a),warn:(...a)=>__console_warn(...a),error:(...a)=>__console_error(...a)};"
    )
    ctx.eval(f"const SANDBOX_ROOT='{sandbox_root}';")

    if allow_network:
        _install_fetch(ctx)

    status = "ok"
    result_text = "undefined"
    try:
        if calls_json:
            ctx.eval(code)
            result_text = _run_calls(ctx, calls_json, result_format)
        else:
            result = ctx.eval(code)
            result_text = _render(result)
    except quickjs.JSException as exc:  # noqa: PERF203
        status = "error"
        result_text = str(exc)
    conn.send((status, result_text, logs))
    conn.close()


def _run_calls(ctx: quickjs.Context, calls_json: str, result_format: str) -> str:
    ctx.eval(JS_CALL_HELPERS)
    ctx.eval(f"const __STEWARD_CALLS = {calls_json};")
    as_json = "true" if result_format == "json" else "false"
    return str(ctx.eval(f"__steward_run_calls(__STEWARD_CALLS, {as_json})"))


def _install_fetch(ctx: quickjs.Context) -> None:
    import requests

    def _fetch(url: str) -> str:
        resp = requests.get(url, timeout=5)
        return resp.text

    ctx.add_callable("__py_fetch", _fetch)
    ctx.eval("async function fetch(u){ return __py_fetch(u); }")
