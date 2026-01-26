"""MCP (Model Context Protocol) server for Steward tools via stdio."""
from __future__ import annotations

import json
import sys
from importlib.metadata import version as pkg_version
from typing import Any, Dict, List, Optional

from .tools import discover_tools
from .types import ToolDefinition

# MCP Protocol version
PROTOCOL_VERSION = "2024-11-05"

def _get_version() -> str:
    """Get package version, with fallback."""
    try:
        return pkg_version("steward")
    except Exception:
        return "0.0.0"


def main() -> None:
    """Run MCP server over stdio."""
    tool_definitions, tool_handlers = discover_tools()
    server = MCPServer(tool_definitions, tool_handlers)
    server.run()


class MCPServer:
    """MCP server implementation using stdio transport."""

    def __init__(self, tool_definitions: List[ToolDefinition], tool_handlers: Dict[str, Any]):
        self.tool_definitions = tool_definitions
        self.tool_handlers = tool_handlers
        self.initialized = False

    def run(self) -> None:
        """Main loop: read JSON-RPC messages from stdin, write responses to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                if response is not None:
                    self._write_response(response)
            except json.JSONDecodeError as e:
                self._write_response(self._error_response(None, -32700, f"Parse error: {e}"))
            except Exception as e:
                self._write_response(self._error_response(None, -32603, f"Internal error: {e}"))

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a JSON-RPC request."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        # Notifications (no id) don't get responses
        is_notification = req_id is None

        if method == "initialize":
            return self._handle_initialize(req_id, params)
        elif method == "initialized":
            # Notification, no response
            self.initialized = True
            return None
        elif method == "tools/list":
            return self._handle_tools_list(req_id)
        elif method == "tools/call":
            return self._handle_tools_call(req_id, params)
        elif method == "ping":
            return self._result_response(req_id, {})
        elif method == "notifications/cancelled":
            # Client cancelled a request, acknowledge
            return None
        else:
            if is_notification:
                return None
            return self._error_response(req_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return self._result_response(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "steward",
                "version": _get_version(),
            },
        })

    def _handle_tools_list(self, req_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = []
        for defn in self.tool_definitions:
            tools.append({
                "name": defn["name"],
                "description": defn.get("description", ""),
                "inputSchema": defn.get("parameters", {"type": "object", "properties": {}}),
            })
        return self._result_response(req_id, {"tools": tools})

    def _handle_tools_call(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._error_response(req_id, -32602, "Missing tool name")

        handler = self.tool_handlers.get(tool_name)
        if not handler:
            return self._error_response(req_id, -32602, f"Unknown tool: {tool_name}")

        try:
            result = handler(arguments)
            output = result.get("output", "")
            is_error = result.get("error", False)

            return self._result_response(req_id, {
                "content": [
                    {"type": "text", "text": output}
                ],
                "isError": is_error,
            })
        except Exception as e:
            return self._result_response(req_id, {
                "content": [
                    {"type": "text", "text": f"Error: {e}"}
                ],
                "isError": True,
            })

    def _result_response(self, req_id: Any, result: Any) -> Dict[str, Any]:
        """Create a successful JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    def _error_response(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _write_response(self, response: Dict[str, Any]) -> None:
        """Write a JSON-RPC response to stdout."""
        sys.stdout.write(json.dumps(response))
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
