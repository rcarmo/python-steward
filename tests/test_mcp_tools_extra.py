"""Additional tests for mcp_list_tools."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_mcp_list_tools_invalid_server_type(tool_handlers, sandbox: Path):
    with pytest.raises(ValueError, match="'server' must be a string"):
        tool_handlers["mcp_list_tools"]({"server": 123})


def test_mcp_call_invalid_args(tool_handlers, sandbox: Path):
    with pytest.raises(ValueError, match="'server' must be a string"):
        tool_handlers["mcp_call"]({"server": None, "tool": "test"})

    with pytest.raises(ValueError, match="'tool' must be a string"):
        tool_handlers["mcp_call"]({"server": "srv", "tool": 123})


@patch("steward.tools.mcp_list_tools.list_tools")
@patch("steward.tools.mcp_list_tools.load_config")
def test_mcp_list_tools_success(mock_config, mock_list, tool_handlers, sandbox: Path):
    mock_config.return_value = {"test-server": MagicMock()}
    mock_list.return_value = [
        {"name": "tool1", "description": "First tool", "inputSchema": {"type": "object", "properties": {"arg1": {"type": "string"}}, "required": ["arg1"]}},
        {"name": "tool2", "description": "Second tool"},
    ]

    result = tool_handlers["mcp_list_tools"]({"server": "test-server"})
    assert "tool1" in result["output"]
    assert "tool2" in result["output"]
    assert "First tool" in result["output"]


@patch("steward.tools.mcp_list_tools.list_tools")
@patch("steward.tools.mcp_list_tools.load_config")
def test_mcp_list_tools_empty(mock_config, mock_list, tool_handlers, sandbox: Path):
    mock_config.return_value = {"test-server": MagicMock()}
    mock_list.return_value = []

    result = tool_handlers["mcp_list_tools"]({"server": "test-server"})
    assert "no tools" in result["output"].lower()


@patch("steward.tools.mcp_list_tools.list_tools")
@patch("steward.tools.mcp_list_tools.load_config")
def test_mcp_list_tools_error(mock_config, mock_list, tool_handlers, sandbox: Path):
    mock_config.return_value = {"test-server": MagicMock()}
    mock_list.side_effect = Exception("Connection failed")

    result = tool_handlers["mcp_list_tools"]({"server": "test-server"})
    assert result.get("error") is True
    assert "Failed to connect" in result["output"]
