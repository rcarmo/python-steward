"""get_python_executable_details tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..types import ToolResult


def env_file() -> Path:
    return Path.cwd() / ".steward-env.json"


def _load_executable() -> str:
    env_path = env_file()
    if env_path.exists():
        try:
            data = json.loads(env_path.read_text(encoding="utf8"))
            exe = data.get("pythonExecutable")
            if exe:
                return exe
        except json.JSONDecodeError:
            pass
    return sys.executable


def tool_get_python_executable_details(resourcePath: Optional[str] = None) -> ToolResult:
    """Return the configured Python executable path and version info.

    Args:
        resourcePath: Working directory context
    """
    exe = _load_executable()
    try:
        completed = subprocess.run(
            [exe, "-c", "import sys, json; print(json.dumps({'version': sys.version, 'executable': sys.executable}))"],
            capture_output=True,
            text=True,
            check=True,
        )
        info = completed.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return {"id": "get_python_executable_details", "output": str(exc), "error": True}
    # Do not enforce executable inside workspace; system interpreters are allowed.
    return {"id": "get_python_executable_details", "output": info}
