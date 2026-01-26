"""mcp_list_tools tool - list tools from an MCP server."""
from __future__ import annotations

from typing import Dict

from ..mcp_client import list_tools, load_config
from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "mcp_list_tools",
    "description": "List available tools from an MCP server. Connects to the server if not already connected.",
    "parameters": {
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Name of the MCP server (as configured in mcp.json).",
            },
        },
        "required": ["server"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    server_name = args.get("server")
    if not isinstance(server_name, str):
        raise ValueError("'server' must be a string")

    configs = load_config()
    if server_name not in configs:
        available = ", ".join(configs.keys()) if configs else "(none configured)"
        raise ValueError(f"Unknown server: {server_name}. Available: {available}")

    try:
        tools = list_tools(server_name)
    except Exception as e:
        return {
            "id": "mcp_list_tools",
            "output": f"Failed to connect to {server_name}: {e}",
            "error": True,
        }

    if not tools:
        return {
            "id": "mcp_list_tools",
            "output": f"Server '{server_name}' has no tools available.",
        }

    lines = [f"Tools from '{server_name}' ({len(tools)} total):\n"]

    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "(no description)")
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:97] + "..."
        lines.append(f"  • {name}")
        lines.append(f"    {description}")

        # Show parameters if present
        schema = tool.get("inputSchema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])
        if props:
            param_strs = []
            for pname, pdef in props.items():
                ptype = pdef.get("type", "any")
                req = "*" if pname in required else ""
                param_strs.append(f"{pname}{req}: {ptype}")
            lines.append(f"    params: {', '.join(param_strs)}")
        lines.append("")

    lines.append("Use mcp_call to invoke a tool.")

    return {"id": "mcp_list_tools", "output": "\n".join(lines)}
