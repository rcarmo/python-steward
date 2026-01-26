"""Tests for web_fetch tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_web_fetch_data_url(tool_handlers, sandbox: Path):
    data_url = "data:text/plain;base64,SGVsbG8gV29ybGQ="
    result = tool_handlers["web_fetch"]({"url": data_url})
    assert "Hello World" in result["output"]


def test_web_fetch_data_url_plain(tool_handlers, sandbox: Path):
    data_url = "data:text/plain,Hello%20Test"
    result = tool_handlers["web_fetch"]({"url": data_url})
    assert "Hello Test" in result["output"]


def test_web_fetch_html_to_markdown(tool_handlers, sandbox: Path):
    html = "<html><body><h1>Title</h1><p>Paragraph</p></body></html>"
    data_url = f"data:text/html;base64,{__import__('base64').b64encode(html.encode()).decode()}"
    result = tool_handlers["web_fetch"]({"url": data_url})
    assert "# Title" in result["output"]
    assert "Paragraph" in result["output"]


def test_web_fetch_raw_mode(tool_handlers, sandbox: Path):
    html = "<html><body><p>Test</p></body></html>"
    data_url = f"data:text/html;base64,{__import__('base64').b64encode(html.encode()).decode()}"
    result = tool_handlers["web_fetch"]({"url": data_url, "raw": True})
    assert "<p>Test</p>" in result["output"]


def test_web_fetch_pagination(tool_handlers, sandbox: Path):
    content = "x" * 100
    data_url = f"data:text/plain;base64,{__import__('base64').b64encode(content.encode()).decode()}"
    result = tool_handlers["web_fetch"]({"url": data_url, "max_length": 50})
    assert "truncated" in result["output"]
    assert "start_index=50" in result["output"]


@patch("steward.tools.web_fetch.requests.get")
def test_web_fetch_http(mock_get, tool_handlers, sandbox: Path):
    mock_response = MagicMock()
    mock_response.text = "<html><body><h1>Test</h1></body></html>"
    mock_response.headers = {"content-type": "text/html"}
    mock_get.return_value = mock_response

    result = tool_handlers["web_fetch"]({"url": "https://example.com"})
    assert "# Test" in result["output"]
