"""Tests for utils module."""

from __future__ import annotations

import json


def test_safe_json_dict():
    from steward.utils import safe_json

    data = {"key": "value", "number": 42}
    result = safe_json(data)
    assert result == json.dumps(data)


def test_safe_json_list():
    from steward.utils import safe_json

    data = [1, 2, 3]
    result = safe_json(data)
    assert result == json.dumps(data)


def test_safe_json_invalid():
    from steward.utils import safe_json

    # Non-serializable object
    class Custom:
        pass

    result = safe_json(Custom())
    assert result == "<unserializable>"


def test_safe_json_string():
    from steward.utils import safe_json

    result = safe_json("already a string")
    assert result == '"already a string"'


def test_safe_json_nested():
    from steward.utils import safe_json

    data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
    result = safe_json(data)
    parsed = json.loads(result)
    assert parsed["nested"]["key"] == "value"


def test_safe_json_none():
    from steward.utils import safe_json

    result = safe_json(None)
    assert result == "null"


def test_safe_json_number():
    from steward.utils import safe_json

    assert safe_json(42) == "42"
    assert safe_json(3.14) == "3.14"


def test_truncate_output_short():
    from steward.utils import truncate_output

    result = truncate_output("short text", 100)
    assert result == "short text"
    assert "[truncated]" not in result


def test_truncate_output_long():
    from steward.utils import truncate_output

    long_text = "x" * 200
    result = truncate_output(long_text, 50)
    assert "[truncated]" in result
    assert len(result) < 200
