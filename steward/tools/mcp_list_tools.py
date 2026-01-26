"""mcp_list_tools tool - list tools from an MCP server."""
from __future__ import annotations

from ..mcp_client import list_tools, load_config
from ..types import ToolResult


def tool_handler(server: str) -> ToolResult:
    """List available tools from an MCP server. Connects to the server if not already connected.

    Args:
        server: Name of the MCP server as configured in mcp.json
    """
    configs = load_config()
    if server not in configs:
        available = ", ".join(configs.keys()) if configs else "(none configured)"
        raise ValueError(f"Unknown server: {server}. Available: {available}")

    try:
        tools = list_tools(server)
    except Exception as e:
        return {
            "id": "mcp_list_tools",
            "output": f"Failed to connect to {server}: {e}",
            "error": True,
        }

    if not tools:
        return {
            "id": "mcp_list_tools",
            "output": f"Server '{server}' has no tools available.",
        }

    lines = [f"Tools from '{server}' ({len(tools)} total):\n"]

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
