"""Tests for interactive bash tools (write_bash, read_bash, stop_bash, list_bash)."""
import os

import pytest

from steward.tools.bash import _sessions, _sessions_lock
from steward.tools.bash import tool_bash as bash_handler
from steward.tools.list_bash import tool_list_bash as list_handler
from steward.tools.read_bash import tool_read_bash as read_handler
from steward.tools.stop_bash import tool_stop_bash as stop_handler
from steward.tools.write_bash import _expand_special_keys
from steward.tools.write_bash import tool_write_bash as write_handler


@pytest.fixture(autouse=True)
def enable_execute():
    """Enable execution for tests."""
    old_val = os.environ.get("STEWARD_ALLOW_EXECUTE")
    os.environ["STEWARD_ALLOW_EXECUTE"] = "1"
    yield
    if old_val is None:
        os.environ.pop("STEWARD_ALLOW_EXECUTE", None)
    else:
        os.environ["STEWARD_ALLOW_EXECUTE"] = old_val


@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Clean up sessions after each test."""
    yield
    with _sessions_lock:
        for sid, info in list(_sessions.items()):
            proc = info["proc"]
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        _sessions.clear()


def test_async_session_lifecycle():
    """Test creating, reading, and stopping an async session."""
    # Start async session
    result = bash_handler(command="echo hello && sleep 0.5 && echo world", mode="async")
    assert "sessionId" in result["output"]
    session_id = result["output"].split("sessionId: ")[1].split(")")[0]

    # List sessions
    list_result = list_handler()
    assert session_id in list_result["output"]

    # Read output (wait for completion)
    read_result = read_handler(sessionId=session_id, delay=2)
    assert "hello" in read_result["output"]

    # Stop session (should already be completed)
    stop_result = stop_handler(sessionId=session_id)
    assert "completed" in stop_result["output"] or "terminated" in stop_result["output"]


def test_read_nonexistent_session():
    """Test reading from a non-existent session."""
    result = read_handler(sessionId="nonexistent")
    assert "not found" in result["output"]


def test_stop_nonexistent_session():
    """Test stopping a non-existent session."""
    result = stop_handler(sessionId="nonexistent")
    assert "not found" in result["output"]


def test_list_no_sessions():
    """Test listing when no sessions exist."""
    result = list_handler()
    assert "No active sessions" in result["output"]


def test_write_to_session():
    """Test writing input to an async session."""
    # Start a cat process that echoes input
    result = bash_handler(command="cat", mode="async")
    session_id = result["output"].split("sessionId: ")[1].split(")")[0]

    # Write to it
    write_result = write_handler(sessionId=session_id, input="test input\n", delay=1)
    # Process may or may not have output yet, but shouldn't error
    assert "write_bash" == write_result["id"]

    # Stop it
    stop_handler(sessionId=session_id)


def test_write_nonexistent_session():
    """Test writing to a non-existent session."""
    result = write_handler(sessionId="nonexistent", input="test")
    assert "not found" in result["output"]


def test_expand_special_keys():
    """Test special key expansion."""
    assert _expand_special_keys("hello{enter}") == "hello\n"
    assert _expand_special_keys("{up}{down}") == "\x1b[A\x1b[B"
    assert _expand_special_keys("a{backspace}b") == "a\x7fb"
