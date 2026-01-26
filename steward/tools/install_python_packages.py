"""install_python_packages tool."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

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


def tool_install_python_packages(packageList: List[str], resourcePath: Optional[str] = None) -> ToolResult:
    """Install Python packages via pip.

    Args:
        packageList: List of package names to install (e.g., ['requests', 'numpy'])
        resourcePath: Working directory context
    """
    if not packageList or not all(isinstance(p, str) for p in packageList):
        raise ValueError("'packageList' must be an array of strings")

    exe = _load_executable()
    cmd: List[str] = [exe, "-m", "pip", "install", *packageList]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = completed.stdout.strip()
        error = False
    except subprocess.CalledProcessError as exc:
        output = f"{exc.stdout}\n{exc.stderr}".strip()
        error = True
    # Allow system interpreter; do not enforce workspace containment.
    return {"id": "install_python_packages", "output": output, "error": error}
