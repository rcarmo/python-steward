"""configure_python_environment tool."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace


def env_file() -> Path:
    return Path.cwd() / ".steward-env.json"


def _choose_executable(python_env: Optional[str]) -> str:
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


def tool_configure_python_environment(
    resourcePath: Optional[str] = None,
    pythonEnvironment: Optional[str] = None,
) -> ToolResult:
    """Select a Python interpreter for subsequent Python tools to use.

    Args:
        resourcePath: Working directory context
        pythonEnvironment: Path to Python executable or virtual environment
    """
    exe = _choose_executable(pythonEnvironment)
    env_path = env_file()
    ensure_inside_workspace(env_path, must_exist=False)
    data = {"pythonExecutable": exe, "resourcePath": resourcePath}
    env_path.write_text(json.dumps(data, indent=2), encoding="utf8")
    return {"id": "configure_python_environment", "output": exe}
