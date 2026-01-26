"""Tests for MCP client tools."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock


def test_mcp_list_servers_no_config(tool_handlers, sandbox: Path):
    result = tool_handlers["mcp_list_servers"]({})
    assert "No MCP servers configured" in result["output"]


def test_mcp_list_servers_with_config(tool_handlers, sandbox: Path):
    config = {
        "mcpServers": {
            "test-server": {
                "command": "python",
                "args": ["-m", "test_mcp"]
            }
        }
    }
    (sandbox / "mcp.json").write_text(json.dumps(config), encoding="utf8")
    result = tool_handlers["mcp_list_servers"]({})
    assert "test-server" in result["output"]
    assert "not connected" in result["output"]


def test_mcp_list_tools_unknown_server(tool_handlers, sandbox: Path):
    import pytest
    with pytest.raises(ValueError, match="Unknown server"):
        tool_handlers["mcp_list_tools"]({"server": "nonexistent"})


def test_mcp_call_unknown_server(tool_handlers, sandbox: Path):
    import pytest
    with pytest.raises(ValueError, match="Unknown server"):
        tool_handlers["mcp_call"]({"server": "nonexistent", "tool": "test"})


def test_mcp_config_locations(sandbox: Path):
    from steward.mcp_client import load_config

    # Test .steward/mcp.json location
    steward_dir = sandbox / ".steward"
    steward_dir.mkdir()
    config = {"mcpServers": {"server1": {"command": "cmd1"}}}
    (steward_dir / "mcp.json").write_text(json.dumps(config), encoding="utf8")

    configs = load_config()
    assert "server1" in configs

    # Test .vscode/mcp.json location (should not override)
    vscode_dir = sandbox / ".vscode"
    vscode_dir.mkdir()
    config2 = {"mcpServers": {"server2": {"command": "cmd2"}}}
    (vscode_dir / "mcp.json").write_text(json.dumps(config2), encoding="utf8")

    configs = load_config()
    assert "server1" in configs  # First found wins


def test_mcp_client_list_servers():
    from steward.mcp_client import list_servers

    # With no config, should return empty list
    servers = list_servers()
    assert isinstance(servers, list)


def test_mcp_server_config_dataclass():
    from steward.mcp_client import MCPServerConfig

    config = MCPServerConfig(
        name="test",
        command="python",
        args=["-m", "server"],
        cwd="/tmp",
        env={"KEY": "value"}
    )
    assert config.name == "test"
    assert config.command == "python"
    assert config.args == ["-m", "server"]


def test_mcp_connection_dataclass():
    from steward.mcp_client import MCPConnection, MCPServerConfig

    config = MCPServerConfig(name="test", command="cmd")
    mock_proc = MagicMock()

    conn = MCPConnection(config=config, process=mock_proc)
    assert conn.config.name == "test"
    assert conn.request_id == 0
    assert conn.initialized is False


def test_mcp_close_connection_not_found(sandbox: Path):
    from steward.mcp_client import close_connection

    # Should not raise for non-existent connection
    close_connection("nonexistent")


def test_mcp_close_all_connections(sandbox: Path):
    from steward.mcp_client import close_all_connections

    # Should not raise even with no connections
    close_all_connections()
