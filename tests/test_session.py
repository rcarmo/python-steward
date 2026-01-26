"""Tests for session management."""
import json

import pytest

from steward.session import (
    generate_session_id,
    get_plan_content,
    get_session_context,
    init_session,
    list_sessions,
    save_checkpoint,
    save_plan,
)


def test_generate_session_id():
    """Test session ID generation."""
    sid1 = generate_session_id()
    sid2 = generate_session_id()
    assert sid1 != sid2
    assert len(sid1) == 36  # UUID format


def test_init_session_creates_dirs(tmp_path):
    """Test session initialization creates directories."""
    sid = "test-session"
    state = init_session(sid, base_dir=tmp_path)

    session_dir = tmp_path / sid
    assert session_dir.exists()
    assert (session_dir / "checkpoints").exists()
    assert (session_dir / "files").exists()
    assert (session_dir / "state.json").exists()

    assert state["session_id"] == sid
    assert "created" in state
    assert state["checkpoints"] == []


def test_init_session_loads_existing(tmp_path):
    """Test session initialization loads existing state."""
    sid = "test-session"
    init_session(sid, base_dir=tmp_path)

    # Modify state
    session_dir = tmp_path / sid
    state_file = session_dir / "state.json"
    state = json.loads(state_file.read_text())
    state["custom_field"] = "test"
    state_file.write_text(json.dumps(state))

    # Re-init should load existing
    loaded = init_session(sid, base_dir=tmp_path)
    assert loaded["custom_field"] == "test"


def test_save_checkpoint(tmp_path):
    """Test checkpoint saving."""
    sid = "test-session"
    init_session(sid, base_dir=tmp_path)

    cp_id = save_checkpoint(
        sid,
        title="First checkpoint",
        description="Did some work",
        files_changed=["file1.py", "file2.py"],
        base_dir=tmp_path,
    )

    assert cp_id == "001-first-checkpoint"

    # Check checkpoint file
    cp_file = tmp_path / sid / "checkpoints" / f"{cp_id}.md"
    assert cp_file.exists()
    content = cp_file.read_text()
    assert "First checkpoint" in content
    assert "file1.py" in content

    # Check index
    index_file = tmp_path / sid / "checkpoints" / "index.md"
    assert index_file.exists()
    assert cp_id in index_file.read_text()


def test_save_multiple_checkpoints(tmp_path):
    """Test multiple checkpoint saving."""
    sid = "test-session"
    init_session(sid, base_dir=tmp_path)

    save_checkpoint(sid, "First", "desc1", base_dir=tmp_path)
    save_checkpoint(sid, "Second", "desc2", base_dir=tmp_path)
    cp_id = save_checkpoint(sid, "Third", "desc3", base_dir=tmp_path)

    assert cp_id == "003-third"

    state_file = tmp_path / sid / "state.json"
    state = json.loads(state_file.read_text())
    assert len(state["checkpoints"]) == 3


def test_get_session_context(tmp_path):
    """Test session context generation."""
    sid = "test-session"
    init_session(sid, base_dir=tmp_path)
    save_checkpoint(sid, "Test checkpoint", "desc", base_dir=tmp_path)

    context = get_session_context(sid, base_dir=tmp_path)

    assert "<session_context>" in context
    assert "Session folder:" in context
    assert "checkpoints/" in context
    assert "001-test-checkpoint" in context


def test_get_session_context_nonexistent(tmp_path):
    """Test session context for non-existent session."""
    context = get_session_context("nonexistent", base_dir=tmp_path)
    assert context == ""


def test_save_and_get_plan(tmp_path):
    """Test plan save and retrieval."""
    sid = "test-session"
    init_session(sid, base_dir=tmp_path)

    plan_content = "# Plan\n\n- [ ] Task 1\n- [ ] Task 2"
    path = save_plan(sid, plan_content, base_dir=tmp_path)

    assert "plan.md" in path

    retrieved = get_plan_content(sid, base_dir=tmp_path)
    assert retrieved == plan_content


def test_get_plan_nonexistent(tmp_path):
    """Test plan retrieval when no plan exists."""
    sid = "test-session"
    init_session(sid, base_dir=tmp_path)

    plan = get_plan_content(sid, base_dir=tmp_path)
    assert plan is None


def test_list_sessions(tmp_path):
    """Test listing sessions."""
    init_session("session1", base_dir=tmp_path)
    init_session("session2", base_dir=tmp_path)
    init_session("session3", base_dir=tmp_path)

    sessions = list_sessions(base_dir=tmp_path)
    assert len(sessions) == 3
    session_ids = [s["session_id"] for s in sessions]
    assert "session1" in session_ids
    assert "session2" in session_ids
    assert "session3" in session_ids


def test_list_sessions_empty(tmp_path):
    """Test listing sessions when none exist."""
    sessions = list_sessions(base_dir=tmp_path)
    assert sessions == []


def test_checkpoint_not_found(tmp_path):
    """Test checkpoint save on non-existent session."""
    with pytest.raises(ValueError, match="not found"):
        save_checkpoint("nonexistent", "title", "desc", base_dir=tmp_path)
