from __future__ import annotations


def test_run_js(tool_handlers):
    result = tool_handlers["run_js"]({"code": "console.log('hi'); 1 + 2;"})
    assert "status: ok" in result["output"]
    assert "result: 3" in result["output"]
    assert "console:" in result["output"]
    assert "log: hi" in result["output"]


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
