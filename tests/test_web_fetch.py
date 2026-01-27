"""Tests for web_fetch tool."""
from __future__ import annotations

import base64

import pytest

from steward.tools.web_fetch import tool_web_fetch


class MockResponse:
    """Mock aiohttp response."""
    def __init__(self, text: str, content_type: str = "text/html"):
        self._text = text
        self.headers = {"content-type": content_type}

    async def text(self):
        return self._text

    def raise_for_status(self):
        pass


class MockClientSession:
    """Mock aiohttp ClientSession."""
    def __init__(self, response_text: str = "", content_type: str = "text/html", raise_error: Exception | None = None):
        self._response_text = response_text
        self._content_type = content_type
        self._raise_error = raise_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def get(self, *args, **kwargs):
        return MockContextManager(self._response_text, self._content_type, self._raise_error)


class MockContextManager:
    """Mock context manager for aiohttp get."""
    def __init__(self, response_text: str, content_type: str, raise_error: Exception | None):
        self._response_text = response_text
        self._content_type = content_type
        self._raise_error = raise_error

    async def __aenter__(self):
        if self._raise_error:
            raise self._raise_error
        return MockResponse(self._response_text, self._content_type)

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("data_url,expected", [
    ("data:text/plain;base64,SGVsbG8gV29ybGQ=", "Hello World"),
    ("data:text/plain,Hello%20Test", "Hello Test"),
])
async def test_web_fetch_data_url(data_url, expected):
    result = await tool_web_fetch(data_url)
    assert expected in result["output"]


@pytest.mark.asyncio
@pytest.mark.parametrize("html,raw,expected", [
    ("<html><body><h1>Title</h1><p>Paragraph</p></body></html>", False, "# Title"),
    ("<html><body><p>Test</p></body></html>", True, "<p>Test</p>"),
])
async def test_web_fetch_html_conversion(html, raw, expected):
    data_url = f"data:text/html;base64,{base64.b64encode(html.encode()).decode()}"
    result = await tool_web_fetch(data_url, raw=raw)
    assert expected in result["output"]


@pytest.mark.asyncio
async def test_web_fetch_pagination():
    content = "x" * 100
    data_url = f"data:text/plain;base64,{base64.b64encode(content.encode()).decode()}"
    result = await tool_web_fetch(data_url, max_length=50)
    assert "truncated" in result["output"]
    assert "start_index=50" in result["output"]


@pytest.mark.asyncio
async def test_web_fetch_http(monkeypatch):
    monkeypatch.setattr("steward.tools.web_fetch.aiohttp.ClientSession",
                        lambda: MockClientSession("<html><body><h1>Test</h1></body></html>"))

    result = await tool_web_fetch("https://example.com")
    assert "# Test" in result["output"]
