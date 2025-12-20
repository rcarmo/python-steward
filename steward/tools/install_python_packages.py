"""install_python_packages tool."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace

TOOL_DEFINITION: ToolDefinition = {
    "name": "install_python_packages",
    "description": "Install Python packages into the configured interpreter environment",
    "parameters": {
        "type": "object",
        "properties": {
            "packageList": {
                "type": "array",
                "items": {"type": "string"},
            },
            "resourcePath": {"type": "string"},
        },
        "required": ["packageList"],
    },
}

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


def tool_handler(args: Dict) -> ToolResult:
    packages = args.get("packageList") if isinstance(args.get("packageList"), list) else None
    if not packages or not all(isinstance(p, str) for p in packages):
        raise ValueError("'packageList' must be an array of strings")
    _ = args.get("resourcePath") if isinstance(args.get("resourcePath"), str) else None

    exe = _load_executable()
    cmd: List[str] = [exe, "-m", "pip", "install", *packages]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = completed.stdout.strip()
        error = False
    except subprocess.CalledProcessError as exc:
        output = f"{exc.stdout}\n{exc.stderr}".strip()
        error = True
    # Allow system interpreter; do not enforce workspace containment.
    return {"id": "install_python_packages", "output": output, "error": error}
