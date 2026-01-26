"""mcp_call tool - invoke a tool on an MCP server."""
from __future__ import annotations

from typing import Dict

from ..mcp_client import call_tool, load_config
from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "mcp_call",
    "description": "Call a tool on an MCP server. Use mcp_list_tools to discover available tools first.",
    "parameters": {
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Name of the MCP server (as configured in mcp.json).",
            },
            "tool": {
                "type": "string",
                "description": "Name of the tool to call.",
            },
            "arguments": {
                "type": "object",
                "description": "Arguments to pass to the tool.",
            },
        },
        "required": ["server", "tool"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    server_name = args.get("server")
    tool_name = args.get("tool")
    arguments = args.get("arguments", {})

    if not isinstance(server_name, str):
        raise ValueError("'server' must be a string")
    if not isinstance(tool_name, str):
        raise ValueError("'tool' must be a string")
    if not isinstance(arguments, dict):
        raise ValueError("'arguments' must be an object")

    configs = load_config()
    if server_name not in configs:
        available = ", ".join(configs.keys()) if configs else "(none configured)"
        raise ValueError(f"Unknown server: {server_name}. Available: {available}")

    try:
        result = call_tool(server_name, tool_name, arguments)
        return {"id": "mcp_call", "output": result}
    except Exception as e:
        return {
            "id": "mcp_call",
            "output": f"Error calling {tool_name} on {server_name}: {e}",
            "error": True,
        }
