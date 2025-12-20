from __future__ import annotations

import urllib.parse


def test_fetch_data_data_url(tool_handlers):
    result = tool_handlers["fetch_data"]({"url": "data:text/plain,hello", "maxBytes": 100})
    assert "hello" in result["output"]


def test_fetch_data_strip_html(tool_handlers):
    html = "<html><body><p>Hello World</p></body></html>"
    encoded = urllib.parse.quote(html)
    result = tool_handlers["fetch_data"]({"url": f"data:text/html,{encoded}", "textOnly": True})
    assert "content-type: text/html" in result["output"]
    assert "bytes: " in result["output"]
    assert "Hello World" in result["output"]
    assert "<html>" not in result["output"]
