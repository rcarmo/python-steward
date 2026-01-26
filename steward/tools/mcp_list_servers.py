"""mcp_list_servers tool - list configured MCP servers."""
from __future__ import annotations

from ..mcp_client import CONFIG_LOCATIONS, list_servers, load_config
from ..types import ToolResult


def tool_mcp_list_servers() -> ToolResult:
    """List configured MCP servers. Shows server name, command, connection status, and available tool count."""
    configs = load_config()

    if not configs:
        locations = ", ".join(CONFIG_LOCATIONS)
        return {
            "id": "mcp_list_servers",
            "output": f"No MCP servers configured. Create a config file at one of: {locations}\n\nExample config:\n{{\n  \"mcpServers\": {{\n    \"example\": {{\n      \"command\": \"python\",\n      \"args\": [\"-m\", \"some_mcp_server\"]\n    }}\n  }}\n}}",
        }

    servers = list_servers()
    lines = ["Configured MCP servers:\n"]

    for server in servers:
        status = "✓ connected" if server["connected"] else "○ not connected"
        tools = f" ({server['tool_count']} tools)" if server["connected"] else ""
        cmd = f"{server['command']} {' '.join(server['args'])}".strip()
        lines.append(f"  {server['name']}: {status}{tools}")
        lines.append(f"    command: {cmd}")

    lines.append("\nUse mcp_list_tools to see available tools from a server.")

    return {"id": "mcp_list_servers", "output": "\n".join(lines), "next_tool": ["mcp_list_tools"]}
