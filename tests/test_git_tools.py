"""Tests for git tools."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(sandbox: Path):
    """Initialize a git repository in sandbox."""
    subprocess.run(["git", "init"], cwd=sandbox, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=sandbox, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=sandbox, check=True)
    return sandbox


def test_git_status_and_diff(tool_handlers, git_repo: Path):
    (git_repo / "g.txt").write_text("one\n", encoding="utf8")
    subprocess.run(["git", "add", "g.txt"], cwd=git_repo, check=True)

    status = tool_handlers["git_status"]({"path": str(git_repo)})
    assert "##" in status["output"]

    (git_repo / "g.txt").write_text("two\n", encoding="utf8")
    diff = tool_handlers["git_diff"]({"path": str(git_repo), "file": "g.txt"})
    assert "-one" in diff["output"]
    assert "+two" in diff["output"]


def test_git_commit(tool_handlers, git_repo: Path):
    (git_repo / "c.txt").write_text("one\n", encoding="utf8")
    subprocess.run(["git", "add", "c.txt"], cwd=git_repo, check=True)

    commit = tool_handlers["git_commit"]({"path": str(git_repo), "message": "init commit"})
    assert "exit 0" in commit["output"]

    status = tool_handlers["git_status"]({"path": str(git_repo)})
    assert "??" not in status["output"]


def test_git_stash(tool_handlers, git_repo: Path):
    file_path = git_repo / "s.txt"
    file_path.write_text("base\n", encoding="utf8")
    subprocess.run(["git", "add", "s.txt"], cwd=git_repo, check=True)
    tool_handlers["git_commit"]({"path": str(git_repo), "message": "base"})

    file_path.write_text("changed\n", encoding="utf8")
    stash_save = tool_handlers["git_stash"]({"path": str(git_repo), "action": "save", "message": "wip"})
    assert "exit 0" in stash_save["output"]
    assert file_path.read_text(encoding="utf8").strip() == "base"

    stash_pop = tool_handlers["git_stash"]({"path": str(git_repo), "action": "pop"})
    assert "exit 0" in stash_pop["output"]
    assert file_path.read_text(encoding="utf8").strip() == "changed"
