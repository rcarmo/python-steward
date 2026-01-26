"""Tests for web_search tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


@patch("steward.tools.web_search.requests.get")
def test_web_search_returns_meta_tool(mock_get, tool_handlers, sandbox: Path):
    # Mock DuckDuckGo response with result
    mock_response = MagicMock()
    mock_response.text = '''
    <div class="result">
        <a class="result__a" href="https://example.com">Example Title</a>
        <a class="result__snippet">This is the snippet text.</a>
    </div>
    '''
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = tool_handlers["web_search"]({"query": "test query"})

    # Should return meta_prompt for LLM synthesis
    assert "meta_prompt" in result
    assert "test query" in result["meta_prompt"]


@patch("steward.tools.web_search.requests.get")
def test_web_search_no_results(mock_get, tool_handlers, sandbox: Path):
    mock_response = MagicMock()
    mock_response.text = "<html><body>No results</body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = tool_handlers["web_search"]({"query": "xyznonexistent123"})
    assert "No results found" in result["output"]


@patch("steward.tools.web_search.requests.get")
def test_web_search_network_error(mock_get, tool_handlers, sandbox: Path):
    import requests
    mock_get.side_effect = requests.RequestException("Network error")

    result = tool_handlers["web_search"]({"query": "test"})
    assert "[error]" in result["output"]
