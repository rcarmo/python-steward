from __future__ import annotations

import pytest


def test_creates_nested_directory(tool_handlers, sandbox):
    result = tool_handlers["create_directory"]({"path": "nested/sub"})
    assert "nested/sub" in result["output"]
    assert (sandbox / "nested" / "sub").is_dir()


def test_fail_without_parents(tool_handlers, sandbox):
    with pytest.raises(Exception):
        tool_handlers["create_directory"]({"path": "a/b", "parents": False})


def test_exist_ok_flag(tool_handlers, sandbox):
    tool_handlers["create_directory"]({"path": "again"})
    with pytest.raises(Exception):
        tool_handlers["create_directory"]({"path": "again"})
    result = tool_handlers["create_directory"]({"path": "again", "existOk": True})
    assert "again" in result["output"]
