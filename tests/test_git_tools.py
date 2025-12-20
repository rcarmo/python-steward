from __future__ import annotations

import subprocess
from pathlib import Path


def init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)


def test_git_status_and_diff(tool_handlers, sandbox: Path):
    repo = sandbox
    init_git_repo(repo)
    (repo / "g.txt").write_text("one\n", encoding="utf8")
    subprocess.run(["git", "add", "g.txt"], cwd=repo, check=True)
    status = tool_handlers["git_status"]({"path": str(repo)})
    assert "##" in status["output"]
    (repo / "g.txt").write_text("two\n", encoding="utf8")
    diff = tool_handlers["git_diff"]({"path": str(repo), "file": "g.txt"})
    assert "-one" in diff["output"]
    assert "+two" in diff["output"]


def test_git_commit(tool_handlers, sandbox: Path):
    repo = sandbox
    init_git_repo(repo)
    (repo / "c.txt").write_text("one\n", encoding="utf8")
    subprocess.run(["git", "add", "c.txt"], cwd=repo, check=True)
    commit = tool_handlers["git_commit"]({"path": str(repo), "message": "init commit"})
    assert "exit 0" in commit["output"]
    status = tool_handlers["git_status"]({"path": str(repo)})
    assert "??" not in status["output"]


def test_git_stash(tool_handlers, sandbox: Path):
    repo = sandbox
    init_git_repo(repo)
    file_path = repo / "s.txt"
    file_path.write_text("base\n", encoding="utf8")
    subprocess.run(["git", "add", "s.txt"], cwd=repo, check=True)
    tool_handlers["git_commit"]({"path": str(repo), "message": "base"})
    file_path.write_text("changed\n", encoding="utf8")
    stash_save = tool_handlers["git_stash"]({"path": str(repo), "action": "save", "message": "wip"})
    assert "exit 0" in stash_save["output"]
    assert file_path.read_text(encoding="utf8").strip() == "base"
    stash_pop = tool_handlers["git_stash"]({"path": str(repo), "action": "pop"})
    assert "exit 0" in stash_pop["output"]
    assert file_path.read_text(encoding="utf8").strip() == "changed"
