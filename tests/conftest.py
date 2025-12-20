from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict

import pytest

from steward.tools import discover_tools
from steward.types import ToolHandler


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root_cwd = Path.cwd()
    original_env = dict(os.environ)
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(root_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture(scope="session")
def tool_handlers() -> Dict[str, ToolHandler]:
    _, handlers = discover_tools()
    return handlers
