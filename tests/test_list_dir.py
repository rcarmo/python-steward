from __future__ import annotations

from pathlib import Path


def test_list_dir(tool_handlers, sandbox: Path):
    (sandbox / "dir" / ".git").mkdir(parents=True)
    (sandbox / "dir" / "node_modules").mkdir(parents=True)
    (sandbox / "dir" / "file.txt").write_text("x", encoding="utf8")
    result = tool_handlers["list_dir"]({"path": "dir"})
    assert "file.txt" in result["output"]
    assert "node_modules/" not in result["output"]
    assert ".git/" not in result["output"]
    all_entries = tool_handlers["list_dir"]({"path": "dir", "includeIgnored": True})
    assert "node_modules/" in all_entries["output"]
    assert ".git/" in all_entries["output"]
