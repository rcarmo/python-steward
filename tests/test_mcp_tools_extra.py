"""Additional tests for mcp_list_tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    "tool,args",
    [
        ("mcp_list_tools", {"server": ""}),
        ("mcp_list_tools", {"server": "nonexistent"}),
        ("mcp_call", {"server": "nonexistent", "tool": "test"}),
    ],
)
def test_mcp_tools_invalid_server(tool_handlers, sandbox: Path, tool, args):
    """Test that invalid server names raise ValueError."""
    with pytest.raises(ValueError, match="Unknown server"):
        tool_handlers[tool](args)


@patch("steward.tools.mcp_list_tools.list_tools")
@patch("steward.tools.mcp_list_tools.load_config")
def test_mcp_list_tools_success(mock_config, mock_list, tool_handlers, sandbox: Path):
    mock_config.return_value = {"test-server": MagicMock()}
    mock_list.return_value = [
        {
            "name": "tool1",
            "description": "First tool",
            "inputSchema": {"type": "object", "properties": {"arg1": {"type": "string"}}, "required": ["arg1"]},
        },
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
