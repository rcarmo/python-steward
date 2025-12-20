from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)


def test_fetch_webpage_data_url(tool_handlers):
    html = "<html><body><p>Hello</p></body></html>"
    data_url = f"data:text/html,{html}"
    res = tool_handlers["fetch_webpage"]({"urls": [data_url], "textOnly": True, "maxBytes": 200})
    assert "Hello" in res["output"]
    assert "content-type: text/html" in res["output"]


def test_file_search(tool_handlers, sandbox: Path):
    (sandbox / "a.txt").write_text("one", encoding="utf8")
    (sandbox / "b.md").write_text("two", encoding="utf8")
    (sandbox / "sub").mkdir()
    (sandbox / "sub" / "c.txt").write_text("three", encoding="utf8")
    results = tool_handlers["file_search"]({"query": "**/*.txt"})
    assert "a.txt" in results["output"]
    assert "sub/c.txt" in results["output"]


def test_get_changed_files(tool_handlers, sandbox: Path):
    repo = sandbox
    init_git_repo(repo)
    (repo / "f.txt").write_text("base", encoding="utf8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    staged = tool_handlers["get_changed_files"]({"repositoryPath": str(repo), "sourceControlState": ["staged"]})
    assert "staged:" in staged["output"]
    (repo / "u.txt").write_text("new", encoding="utf8")
    untracked = tool_handlers["get_changed_files"]({"repositoryPath": str(repo), "sourceControlState": ["untracked"]})
    assert "untracked:" in untracked["output"]


def test_list_code_usages(tool_handlers, sandbox: Path):
    (sandbox / "x.py").write_text("def Target():\n    pass\n", encoding="utf8")
    (sandbox / "y.py").write_text("# Target reference\n", encoding="utf8")
    hits = tool_handlers["list_code_usages"]({"symbolName": "Target", "maxResults": 5})
    assert "x.py" in hits["output"]
    assert "y.py" in hits["output"]


def test_manage_todo_list(tool_handlers, sandbox: Path):
    todo = [{"id": 1, "title": "t1", "description": "d1", "status": "not-started"}]
    res = tool_handlers["manage_todo_list"]({"todoList": todo})
    assert "[not-started] t1" in res["output"]
    plan_path = sandbox / ".steward-plan.json"
    assert plan_path.exists()


def test_configure_and_get_python_details(tool_handlers, sandbox: Path):
    cfg = tool_handlers["configure_python_environment"]({})
    assert cfg["output"]
    details = tool_handlers["get_python_executable_details"]({})
    info = json.loads(details["output"])
    assert "version" in info
    assert info.get("executable")


def test_install_python_packages_failure(tool_handlers, sandbox: Path, monkeypatch):
    monkeypatch.setenv("PIP_NO_INDEX", "1")
    res = tool_handlers["install_python_packages"]({"packageList": ["nonexistent-pkg-for-steward-tests"]})
    assert res.get("error") is True
    assert res["output"]
