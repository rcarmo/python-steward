"""Tests for run_js tool."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "code,expected_status,expected_result,expected_log",
    [
        ("console.log('hi'); 1 + 2;", "status: ok", "result: 3", "log: hi"),
    ],
)
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


@pytest.mark.parametrize(
    "args,expected_parts",
    [
        (
            {
                "code": "function transform(input){ return {value: input.text.toUpperCase()}; }",
                "function": "transform",
                "params": {"text": "hello"},
            },
            ["status: ok", 'result: {"value":"HELLO"}'],
        ),
        (
            {
                "code": "var t = { sum: ({a,b}) => a + b, greet: ({name}) => `hi ${name}` };",
                "calls": [
                    {"function": "t.sum", "params": {"a": 2, "b": 3}},
                    {"function": "t.greet", "params": {"name": "Ada"}},
                ],
                "resultFormat": "text",
            },
            ["status: ok", "result: 5", "hi Ada"],
        ),
        (
            {
                "code": "function transformText(input){ return input.text.replace(/\\bfoo\\b/g, 'bar'); }",
                "function": "transformText",
                "params": {"text": "foo baz foo"},
                "resultFormat": "text",
            },
            ["status: ok", "result: bar baz bar"],
        ),
        (
            {
                "code": "function transformJson(input){ return {name: input.name.toUpperCase(), items: input.items.map((item) => item * 2)}; }",
                "function": "transformJson",
                "params": {"name": "ada", "items": [1, 2]},
            },
            ["status: ok", 'result: {"name":"ADA","items":[2,4]}'],
        ),
        (
            {
                "code": "function transformYaml(input){ return input.yaml.replace(/name:\\s*\\w+/, 'name: Ada'); }",
                "function": "transformYaml",
                "params": {"yaml": "name: Bob\\nage: 30\\n"},
                "resultFormat": "text",
            },
            ["status: ok", "result: name: Ada", "age: 30"],
        ),
    ],
)
def test_run_js_transformers(tool_handlers, args, expected_parts):
    result = tool_handlers["run_js"](args)
    for part in expected_parts:
        assert part in result["output"]
