"""Tests for bash tool."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def enable_execute():
    """Enable execute for bash tests."""
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    yield
    # Cleanup any test-specific env vars
    for key in ["STEWARD_EXEC_ALLOW", "STEWARD_EXEC_DENY", "STEWARD_EXEC_AUDIT"]:
        os.environ.pop(key, None)


@pytest.mark.parametrize("command,expected", [
    ("echo hello", "hello"),
])
def test_bash_runs_command(tool_handlers, sandbox: Path, enable_execute, command, expected):
    result = tool_handlers["bash"]({"command": command})
    assert expected in result["output"]


def test_bash_gated(tool_handlers):
    os.environ.pop("STEWARD_ALLOW_EXECUTE", None)
    with pytest.raises(ValueError, match="disabled"):
        tool_handlers["bash"]({"command": "echo test"})


def test_bash_with_cwd(tool_handlers, sandbox: Path, enable_execute):
    (sandbox / "sub").mkdir()
    result = tool_handlers["bash"]({"command": "pwd", "cwd": "sub"})
    assert "sub" in result["output"]


@pytest.mark.parametrize("mode,detach,expected", [
    ("sync", False, "still running"),
    ("async", False, "Started async"),
    ("async", True, "Started detached"),
])
def test_bash_modes(tool_handlers, sandbox: Path, enable_execute, mode, detach, expected):
    args = {"command": "sleep 5" if mode == "sync" else "sleep 1", "mode": mode}
    if mode == "sync":
        args["initial_wait"] = 0.5
    if detach:
        args["detach"] = True
    result = tool_handlers["bash"](args)
    assert expected in result["output"]


def test_bash_allow_deny(tool_handlers, sandbox: Path, enable_execute):
    os.environ["STEWARD_EXEC_ALLOW"] = "echo"
    with pytest.raises(ValueError, match="not allowed"):
        tool_handlers["bash"]({"command": "pwd"})
    result = tool_handlers["bash"]({"command": "echo ok"})
    assert "ok" in result["output"]
    del os.environ["STEWARD_EXEC_ALLOW"]

    os.environ["STEWARD_EXEC_DENY"] = "pwd"
    with pytest.raises(ValueError, match="blocked"):
        tool_handlers["bash"]({"command": "pwd"})


def test_bash_audit_log(tool_handlers, sandbox: Path, enable_execute):
    os.environ["STEWARD_EXEC_AUDIT"] = "1"
    tool_handlers["bash"]({"command": "echo hi"})
    log_path = sandbox / ".steward-exec-audit.log"
    assert log_path.exists()
    assert "echo hi" in log_path.read_text(encoding="utf8")
