from __future__ import annotations

import os
from pathlib import Path

import pytest

from steward.tools.run_in_terminal import TOOL_DEFINITION  # noqa: F401


def test_runs_command(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    result = tool_handlers["run_in_terminal"]({"command": "pwd"})
    assert "exit 0" in result["output"]
    assert str(sandbox) in result["output"]


def test_gated_execute(tool_handlers):
    if "STEWARD_ALLOW_EXECUTE" in os.environ:
        del os.environ["STEWARD_ALLOW_EXECUTE"]
    with pytest.raises(Exception):
        tool_handlers["run_in_terminal"]({"command": "pwd"})


def test_cwd_env_timeout(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    subdir = sandbox / "sub"
    subdir.mkdir()
    result = tool_handlers["run_in_terminal"]({"command": "pwd", "cwd": "sub", "env": {"FOO": "BAR"}})
    assert "sub" in result["output"]
    timeout_result = tool_handlers["run_in_terminal"]({"command": "sleep", "args": ["2"], "timeoutMs": 100})
    assert "exit" in timeout_result["output"] or timeout_result.get("error")


def test_allow_deny_lists(tool_handlers):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    os.environ["STEWARD_EXEC_ALLOW"] = "echo"
    with pytest.raises(Exception):
        tool_handlers["run_in_terminal"]({"command": "pwd"})
    allowed = tool_handlers["run_in_terminal"]({"command": "echo", "args": ["ok"], "stream": True})
    assert allowed["output"].strip() == "ok"
    os.environ["STEWARD_EXEC_ALLOW"] = ""
    os.environ["STEWARD_EXEC_DENY"] = "pwd"
    with pytest.raises(Exception):
        tool_handlers["run_in_terminal"]({"command": "pwd"})


def test_background(tool_handlers):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    bg = tool_handlers["run_in_terminal"]({"command": "sleep", "args": ["1"], "background": True})
    assert "started pid" in bg["output"]


def test_stream(tool_handlers):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    res = tool_handlers["run_in_terminal"]({"command": "printf", "args": ["hello"], "stream": True})
    assert res["output"].strip() == "hello"


def test_output_cap(tool_handlers):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    res = tool_handlers["run_in_terminal"]({"command": "python", "args": ["-c", "print('x'*50000)"] , "maxOutputBytes": 2000})
    assert "[truncated]" in res["output"]


def test_env_default_cap(tool_handlers):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    os.environ["STEWARD_EXEC_MAX_OUTPUT_BYTES"] = "100"
    res = tool_handlers["run_in_terminal"]({"command": "python", "args": ["-c", "print('x'*5000)"]})
    assert "[truncated]" in res["output"]


def test_audit_log(tool_handlers, sandbox: Path):
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    os.environ["STEWARD_EXEC_AUDIT"] = "1"
    tool_handlers["run_in_terminal"]({"command": "echo", "args": ["hi"], "stream": True})
    log_path = sandbox / ".steward-exec-audit.log"
    assert log_path.exists()
    assert "\"command\": " in log_path.read_text(encoding="utf8")
