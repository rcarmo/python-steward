"""Tests for web_search tool."""
from __future__ import annotations

import pytest

from steward.tools.web_search import tool_web_search


class MockResponse:
    """Mock aiohttp response."""
    def __init__(self, text: str):
        self._text = text

    async def text(self):
        return self._text

    def raise_for_status(self):
        pass


class MockClientSession:
    """Mock aiohttp ClientSession."""
    def __init__(self, response_text: str = "", raise_error: Exception | None = None):
        self._response_text = response_text
        self._raise_error = raise_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def get(self, *args, **kwargs):
        return MockContextManager(self._response_text, self._raise_error)


class MockContextManager:
    """Mock context manager for aiohttp get."""
    def __init__(self, response_text: str, raise_error: Exception | None):
        self._response_text = response_text
        self._raise_error = raise_error

    async def __aenter__(self):
        if self._raise_error:
            raise self._raise_error
        return MockResponse(self._response_text)

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("query,html,expected_in_output", [
    (
        "test query",
        '''<div class="result">
            <a class="result__a" href="https://example.com">Example Title</a>
            <a class="result__snippet">This is the snippet text.</a>
        </div>''',
        "meta_prompt",
    ),
    (
        "xyznonexistent123",
        "<html><body>No results</body></html>",
        "No results found",
    ),
])
async def test_web_search_results(monkeypatch, query, html, expected_in_output):
    monkeypatch.setattr("steward.tools.web_search.aiohttp.ClientSession", lambda: MockClientSession(html))

    result = await tool_web_search(query)

    if expected_in_output == "meta_prompt":
        assert "meta_prompt" in result
        assert query in result["meta_prompt"]
    else:
        assert expected_in_output in result["output"]


@pytest.mark.asyncio
async def test_web_search_network_error(monkeypatch):
    import aiohttp
    monkeypatch.setattr("steward.tools.web_search.aiohttp.ClientSession",
                        lambda: MockClientSession(raise_error=aiohttp.ClientError("Network error")))

    result = await tool_web_search("test")
    assert "[error]" in result["output"]

