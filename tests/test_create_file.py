from __future__ import annotations

from pathlib import Path


def test_create_file(tool_handlers, sandbox: Path):
    file_path = sandbox / "nested" / "created.txt"
    created = tool_handlers["create_file"]({"path": "nested/created.txt", "content": "hello"})
    assert "Created nested/created.txt" in created["output"]
    assert file_path.read_text(encoding="utf8") == "hello"
    try:
        tool_handlers["create_file"]({"path": "nested/created.txt", "content": "again"})
        assert False, "Expected overwrite error"
    except Exception:
        pass
    forced = tool_handlers["create_file"]({"path": "nested/created.txt", "content": "again", "overwrite": True})
    assert "Created nested/created.txt" in forced["output"]
    assert file_path.read_text(encoding="utf8") == "again"
