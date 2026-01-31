from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, Mapping

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


@pytest.fixture()
def enable_execute():
    """Enable execution tools for tests and restore environment."""
    keys = ["STEWARD_ALLOW_EXECUTE", "STEWARD_EXEC_ALLOW", "STEWARD_EXEC_DENY", "STEWARD_EXEC_AUDIT"]
    original = {key: os.environ.get(key) for key in keys}
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture()
def make_file(sandbox: Path):
    """Create a file with given content."""

    def _create(content: str, name: str = "sample.txt") -> Path:
        file_path = sandbox / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf8")
        return file_path

    return _create


@pytest.fixture()
def make_files(sandbox: Path):
    """Create multiple files from a dict or list."""

    def _create(files: Mapping[str, str] | Iterable[str], subdirs: list[str] | None = None) -> None:
        for subdir in subdirs or []:
            (sandbox / subdir).mkdir(parents=True, exist_ok=True)
        if isinstance(files, Mapping):
            for name, content in files.items():
                file_path = sandbox / name
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf8")
        else:
            for name in files:
                file_path = sandbox / name
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("", encoding="utf8")

    return _create


@pytest.fixture()
def mock_aiohttp_session(monkeypatch: pytest.MonkeyPatch):
    """Patch aiohttp.ClientSession for tools that fetch URLs."""

    def _patch(
        target: str,
        response_text: str = "",
        content_type: str = "text/html",
        raise_error: Exception | None = None,
    ) -> None:
        class MockResponse:
            def __init__(self, text: str, content_type_value: str):
                self._text = text
                self.headers = {"content-type": content_type_value}

            async def text(self) -> str:
                return self._text

            def raise_for_status(self) -> None:
                pass

        class MockContextManager:
            def __init__(self, text: str, content_type_value: str, error: Exception | None):
                self._text = text
                self._content_type = content_type_value
                self._error = error

            async def __aenter__(self) -> MockResponse:
                if self._error:
                    raise self._error
                return MockResponse(self._text, self._content_type)

            async def __aexit__(self, *args) -> None:
                pass

        class MockClientSession:
            def __init__(self, text: str, content_type_value: str, error: Exception | None):
                self._text = text
                self._content_type = content_type_value
                self._error = error

            async def __aenter__(self) -> "MockClientSession":
                return self

            async def __aexit__(self, *args) -> None:
                pass

            def get(self, *args, **kwargs) -> MockContextManager:
                return MockContextManager(self._text, self._content_type, self._error)

        monkeypatch.setattr(
            target,
            lambda: MockClientSession(response_text, content_type, raise_error),
        )

    return _patch


@pytest.fixture(scope="session")
def tool_handlers() -> Dict[str, ToolHandler]:
    # Enable execute tools for test discovery
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    # Mock MCP config to enable MCP tools for testing
    import steward.tools.registry as reg

    original_has_mcp = reg._has_mcp_servers
    reg._has_mcp_servers = lambda: True
    try:
        _, handlers = discover_tools()
    finally:
        reg._has_mcp_servers = original_has_mcp
    return handlers
