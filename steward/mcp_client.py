"""MCP client for connecting to external MCP servers."""
from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configuration file locations (VS Code style)
CONFIG_LOCATIONS = [
    ".steward/mcp.json",
    "mcp.json",
    ".vscode/mcp.json",
]


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None


@dataclass
class MCPConnection:
    """Active connection to an MCP server."""
    config: MCPServerConfig
    process: subprocess.Popen
    request_id: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    initialized: bool = False
    tools: List[Dict[str, Any]] = field(default_factory=list)


# Global connection pool
_connections: Dict[str, MCPConnection] = {}
_connections_lock = threading.Lock()


def load_config() -> Dict[str, MCPServerConfig]:
    """Load MCP server configurations from config files."""
    servers: Dict[str, MCPServerConfig] = {}

    for config_path in CONFIG_LOCATIONS:
        path = Path.cwd() / config_path
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf8"))
                mcp_servers = data.get("mcpServers", {})
                for name, config in mcp_servers.items():
                    if isinstance(config, dict) and "command" in config:
                        servers[name] = MCPServerConfig(
                            name=name,
                            command=config["command"],
                            args=config.get("args", []),
                            cwd=config.get("cwd"),
                            env=config.get("env"),
                        )
            except (json.JSONDecodeError, KeyError):
                continue
            break  # Use first found config

    return servers


def get_connection(server_name: str) -> MCPConnection:
    """Get or create a connection to an MCP server."""
    with _connections_lock:
        if server_name in _connections:
            conn = _connections[server_name]
            if conn.process.poll() is None:  # Still running
                return conn
            # Process died, remove it
            del _connections[server_name]

        # Need to create new connection
        configs = load_config()
        if server_name not in configs:
            raise ValueError(f"Unknown MCP server: {server_name}")

        config = configs[server_name]
        conn = _start_server(config)
        _connections[server_name] = conn
        return conn


def _start_server(config: MCPServerConfig) -> MCPConnection:
    """Start an MCP server process and initialize it."""
    cwd = config.cwd or str(Path.cwd())
    env = None
    if config.env:
        import os
        env = os.environ.copy()
        env.update(config.env)

    process = subprocess.Popen(
        [config.command] + config.args,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    conn = MCPConnection(config=config, process=process)

    # Initialize the connection
    _initialize(conn)

    return conn


def _send_request(conn: MCPConnection, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Send a JSON-RPC request and wait for response."""
    with conn.lock:
        conn.request_id += 1
        request_id = conn.request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        # Send request
        request_line = json.dumps(request) + "\n"
        conn.process.stdin.write(request_line)
        conn.process.stdin.flush()

        # Read response
        response_line = conn.process.stdout.readline()
        if not response_line:
            raise RuntimeError(f"No response from MCP server {conn.config.name}")

        response = json.loads(response_line)

        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"MCP error: {error.get('message', 'Unknown error')}")

        return response.get("result", {})


def _send_notification(conn: MCPConnection, method: str, params: Optional[Dict] = None) -> None:
    """Send a JSON-RPC notification (no response expected)."""
    with conn.lock:
        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notification["params"] = params

        notification_line = json.dumps(notification) + "\n"
        conn.process.stdin.write(notification_line)
        conn.process.stdin.flush()


def _initialize(conn: MCPConnection) -> None:
    """Initialize the MCP connection."""
    _send_request(conn, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "steward",
            "version": "0.1.0",
        },
    })

    # Send initialized notification
    _send_notification(conn, "initialized")
    conn.initialized = True

    # Fetch available tools
    tools_result = _send_request(conn, "tools/list")
    conn.tools = tools_result.get("tools", [])


def list_servers() -> List[Dict[str, Any]]:
    """List all configured MCP servers."""
    configs = load_config()
    servers = []
    for name, config in configs.items():
        # Check if connected
        connected = False
        tool_count = 0
        with _connections_lock:
            if name in _connections:
                conn = _connections[name]
                if conn.process.poll() is None:
                    connected = True
                    tool_count = len(conn.tools)

        servers.append({
            "name": name,
            "command": config.command,
            "args": config.args,
            "connected": connected,
            "tool_count": tool_count,
        })
    return servers


def list_tools(server_name: str) -> List[Dict[str, Any]]:
    """List tools available from an MCP server."""
    conn = get_connection(server_name)
    return conn.tools


def call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
    """Call a tool on an MCP server."""
    conn = get_connection(server_name)

    result = _send_request(conn, "tools/call", {
        "name": tool_name,
        "arguments": arguments,
    })

    # Extract text content from response
    content = result.get("content", [])
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(item.get("text", ""))

    return "\n".join(text_parts) if text_parts else str(result)


def close_connection(server_name: str) -> None:
    """Close connection to an MCP server."""
    with _connections_lock:
        if server_name in _connections:
            conn = _connections.pop(server_name)
            if conn.process.poll() is None:
                conn.process.terminate()
                try:
                    conn.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    conn.process.kill()


def close_all_connections() -> None:
    """Close all MCP server connections."""
    with _connections_lock:
        for name in list(_connections.keys()):
            conn = _connections.pop(name)
            if conn.process.poll() is None:
                conn.process.terminate()
                try:
                    conn.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    conn.process.kill()
