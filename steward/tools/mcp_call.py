"""mcp_call tool - invoke a tool on an MCP server."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..mcp_client import call_tool, load_config
from ..types import ToolResult


def tool_mcp_call(server: str, tool: str, arguments: Optional[Dict[str, Any]] = None) -> ToolResult:
    """Call a tool on an MCP server. Use mcp_list_tools to discover available tools first.

    Args:
        server: Name of the MCP server as configured in mcp.json
        tool: Name of the tool to call
        arguments: Arguments to pass to the tool
    """
    args = arguments if arguments is not None else {}

    configs = load_config()
    if server not in configs:
        available = ", ".join(configs.keys()) if configs else "(none configured)"
        raise ValueError(f"Unknown server: {server}. Available: {available}")

    try:
        result = call_tool(server, tool, args)
        return {"id": "mcp_call", "output": result, "next_tool": ["mcp_call"]}
    except Exception as e:
        return {
            "id": "mcp_call",
            "output": f"Error calling {tool} on {server}: {e}",
            "error": True,
        }
