"""Tests for bash tool."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_bash_runs_command(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    result = tool_handlers["bash"]({"command": "echo hello"})
    assert "hello" in result["output"]


def test_bash_gated(tool_handlers):
    if "STEWARD_ALLOW_EXECUTE" in os.environ:
        del os.environ["STEWARD_ALLOW_EXECUTE"]
    with pytest.raises(ValueError, match="disabled"):
        tool_handlers["bash"]({"command": "echo test"})


def test_bash_with_cwd(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    subdir = sandbox / "sub"
    subdir.mkdir()
    result = tool_handlers["bash"]({"command": "pwd", "cwd": "sub"})
    assert "sub" in result["output"]


def test_bash_timeout(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    result = tool_handlers["bash"]({"command": "sleep 5", "initial_wait": 0.5})
    assert "still running" in result["output"]


def test_bash_async(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    result = tool_handlers["bash"]({"command": "sleep 1", "mode": "async"})
    assert "Started async" in result["output"]
    assert "pid" in result["output"]


def test_bash_detach(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    result = tool_handlers["bash"]({"command": "sleep 1", "mode": "async", "detach": True})
    assert "Started detached" in result["output"]


def test_bash_allow_deny(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    os.environ["STEWARD_EXEC_ALLOW"] = "echo"
    with pytest.raises(ValueError, match="not allowed"):
        tool_handlers["bash"]({"command": "pwd"})
    result = tool_handlers["bash"]({"command": "echo ok"})
    assert "ok" in result["output"]
    del os.environ["STEWARD_EXEC_ALLOW"]

    os.environ["STEWARD_EXEC_DENY"] = "pwd"
    with pytest.raises(ValueError, match="blocked"):
        tool_handlers["bash"]({"command": "pwd"})
    del os.environ["STEWARD_EXEC_DENY"]


def test_bash_audit_log(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    os.environ["STEWARD_EXEC_AUDIT"] = "1"
    tool_handlers["bash"]({"command": "echo hi"})
    log_path = sandbox / ".steward-exec-audit.log"
    assert log_path.exists()
    assert "echo hi" in log_path.read_text(encoding="utf8")
