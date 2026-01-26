"""configure_python_environment tool."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace

TOOL_DEFINITION: ToolDefinition = {
    "name": "configure_python_environment",
    "description": "Select a Python interpreter for subsequent Python tools to use.",
    "parameters": {
        "type": "object",
        "properties": {
            "resourcePath": {
                "type": "string",
                "description": "Optional. Working directory context.",
            },
            "pythonEnvironment": {
                "type": "string",
                "description": "Optional. Path to Python executable or virtual environment.",
            },
        },
    },
}

def env_file() -> Path:
    return Path.cwd() / ".steward-env.json"


def _choose_executable(python_env: str | None) -> str:
    if python_env:
        candidate = Path(python_env).expanduser()
        if not candidate.exists():
            raise ValueError("pythonEnvironment not found")
        return str(candidate)
    from_env = os.environ.get("VIRTUAL_ENV")
    if from_env:
        candidate = Path(from_env) / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    which = shutil.which("python3") or shutil.which("python")
    return which or sys.executable


def tool_handler(args: Dict) -> ToolResult:
    python_env = args.get("pythonEnvironment") if isinstance(args.get("pythonEnvironment"), str) else None
    resource_path = args.get("resourcePath") if isinstance(args.get("resourcePath"), str) else None

    exe = _choose_executable(python_env)
    env_path = env_file()
    ensure_inside_workspace(env_path, must_exist=False)
    data = {"pythonExecutable": exe, "resourcePath": resource_path}
    env_path.write_text(json.dumps(data, indent=2), encoding="utf8")
    return {"id": "configure_python_environment", "output": exe}
