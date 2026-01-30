"""Tests for MCP server."""

from __future__ import annotations

from steward.mcp import MCPServer
from steward.tools import discover_tools


def test_mcp_server_initialize():
    defs, handlers = discover_tools()
    server = MCPServer(defs, handlers)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }

    response = server.handle_request(request)
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["serverInfo"]["name"] == "steward"


def test_mcp_server_tools_list():
    defs, handlers = discover_tools()
    server = MCPServer(defs, handlers)

    request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    response = server.handle_request(request)

    assert "result" in response
    tools = response["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "view" in tool_names
    assert "grep" in tool_names
    assert "create" in tool_names


def test_mcp_server_tools_call(sandbox):
    import os

    os.chdir(sandbox)

    defs, handlers = discover_tools()
    server = MCPServer(defs, handlers)

    # Create a test file
    (sandbox / "test.txt").write_text("hello world", encoding="utf8")

    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "view", "arguments": {"path": "test.txt"}},
    }

    response = server.handle_request(request)
    assert "result" in response
    content = response["result"]["content"]
    assert any("hello world" in c.get("text", "") for c in content)


def test_mcp_server_unknown_method():
    defs, handlers = discover_tools()
    server = MCPServer(defs, handlers)

    request = {"jsonrpc": "2.0", "id": 4, "method": "unknown/method"}
    response = server.handle_request(request)

    assert "error" in response
    assert response["error"]["code"] == -32601


def test_mcp_server_unknown_tool():
    defs, handlers = discover_tools()
    server = MCPServer(defs, handlers)

    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}},
    }

    response = server.handle_request(request)
    assert "error" in response
    assert response["error"]["code"] == -32602


def test_mcp_server_ping():
    defs, handlers = discover_tools()
    server = MCPServer(defs, handlers)

    request = {"jsonrpc": "2.0", "id": 6, "method": "ping"}
    response = server.handle_request(request)

    assert response["id"] == 6
    assert response["result"] == {}
