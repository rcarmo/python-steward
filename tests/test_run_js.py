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


def test_run_js_function_call(tool_handlers):
    code = "function transform(input){ return {value: input.text.toUpperCase()}; }"
    result = tool_handlers["run_js"]({
        "code": code,
        "function": "transform",
        "params": {"text": "hello"},
    })
    assert "status: ok" in result["output"]
    assert 'result: {"value":"HELLO"}' in result["output"]


def test_run_js_calls_text(tool_handlers):
    code = "var t = { sum: ({a,b}) => a + b, greet: ({name}) => `hi ${name}` };"
    result = tool_handlers["run_js"]({
        "code": code,
        "calls": [
            {"function": "t.sum", "params": {"a": 2, "b": 3}},
            {"function": "t.greet", "params": {"name": "Ada"}},
        ],
        "resultFormat": "text",
    })
    assert "status: ok" in result["output"]
    assert "result: 5" in result["output"]
    assert "hi Ada" in result["output"]


def test_run_js_transform_text(tool_handlers):
    code = "function transformText(input){ return input.text.replace(/\\bfoo\\b/g, 'bar'); }"
    result = tool_handlers["run_js"]({
        "code": code,
        "function": "transformText",
        "params": {"text": "foo baz foo"},
        "resultFormat": "text",
    })
    assert "status: ok" in result["output"]
    assert "result: bar baz bar" in result["output"]


def test_run_js_transform_json(tool_handlers):
    code = "function transformJson(input){ return {name: input.name.toUpperCase(), items: input.items.map((item) => item * 2)}; }"
    result = tool_handlers["run_js"]({
        "code": code,
        "function": "transformJson",
        "params": {"name": "ada", "items": [1, 2]},
    })
    assert "status: ok" in result["output"]
    assert 'result: {"name":"ADA","items":[2,4]}' in result["output"]


def test_run_js_transform_yaml(tool_handlers):
    code = "function transformYaml(input){ return input.yaml.replace(/name:\\s*\\w+/, 'name: Ada'); }"
    result = tool_handlers["run_js"]({
        "code": code,
        "function": "transformYaml",
        "params": {"yaml": "name: Bob\\nage: 30\\n"},
        "resultFormat": "text",
    })
    assert "status: ok" in result["output"]
    assert "result: name: Ada" in result["output"]
    assert "age: 30" in result["output"]
