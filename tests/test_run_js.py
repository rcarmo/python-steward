"""Tests for run_js tool."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("code,expected_status,expected_result,expected_log", [
    ("console.log('hi'); 1 + 2;", "status: ok", "result: 3", "log: hi"),
])
def test_run_js(tool_handlers, code, expected_status, expected_result, expected_log):
    result = tool_handlers["run_js"]({"code": code})
    assert expected_status in result["output"]
    assert expected_result in result["output"]
    assert expected_log in result["output"]


def test_run_js_timeout(tool_handlers):
    result = tool_handlers["run_js"]({"code": "while(true) {}", "timeoutMs": 50})
    assert result.get("error") is True
    assert "status: timeout" in result["output"] or "status: error" in result["output"]


def test_run_js_from_file(tool_handlers, sandbox):
    js_path = sandbox / "snippet.js"
    js_path.write_text("console.log('from file'); 40 + 2;", encoding="utf8")
    result = tool_handlers["run_js"]({"path": str(js_path)})
    assert "status: ok" in result["output"]
    assert "result: 42" in result["output"]
    assert "log: from file" in result["output"]
