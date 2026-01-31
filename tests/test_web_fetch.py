"""Tests for web_fetch tool."""

from __future__ import annotations

import base64

import pytest

from steward.tools.web_fetch import tool_web_fetch


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data_url,expected",
    [
        ("data:text/plain;base64,SGVsbG8gV29ybGQ=", "Hello World"),
        ("data:text/plain,Hello%20Test", "Hello Test"),
    ],
)
async def test_web_fetch_data_url(data_url, expected):
    result = await tool_web_fetch(data_url)
    assert expected in result["output"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html,raw,expected",
    [
        ("<html><body><h1>Title</h1><p>Paragraph</p></body></html>", False, "# Title"),
        ("<html><body><p>Test</p></body></html>", True, "<p>Test</p>"),
    ],
)
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
async def test_web_fetch_http(mock_aiohttp_session):
    mock_aiohttp_session(
        "steward.tools.web_fetch.aiohttp.ClientSession",
        response_text="<html><body><h1>Test</h1></body></html>",
    )

    result = await tool_web_fetch("https://example.com")
    assert "# Test" in result["output"]
