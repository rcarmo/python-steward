"""Tests for web_search tool."""

from __future__ import annotations

import pytest

from steward.tools.web_search import tool_web_search


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,html,expected_in_output",
    [
        (
            "test query",
            """<div class="result">
            <a class="result__a" href="https://example.com">Example Title</a>
            <a class="result__snippet">This is the snippet text.</a>
        </div>""",
            "meta_prompt",
        ),
        (
            "xyznonexistent123",
            "<html><body>No results</body></html>",
            "No results found",
        ),
    ],
)
async def test_web_search_results(mock_aiohttp_session, query, html, expected_in_output):
    mock_aiohttp_session("steward.tools.web_search.aiohttp.ClientSession", response_text=html)

    result = await tool_web_search(query)

    if expected_in_output == "meta_prompt":
        assert "meta_prompt" in result
        assert query in result["meta_prompt"]
    else:
        assert expected_in_output in result["output"]


@pytest.mark.asyncio
async def test_web_search_network_error(mock_aiohttp_session):
    import aiohttp

    mock_aiohttp_session(
        "steward.tools.web_search.aiohttp.ClientSession",
        raise_error=aiohttp.ClientError("Network error"),
    )

    result = await tool_web_search("test")
    assert "[error]" in result["output"]
