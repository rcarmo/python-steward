# Protocol Support

Steward supports multiple protocols for integration with different clients and tools.

## MCP Server Mode

Steward can run as an MCP (Model Context Protocol) server over stdio, exposing all tools to MCP-compatible clients:

```bash
# Run as MCP server
python3 -m steward.mcp

# Or via entry point after install
steward-mcp
```

### MCP Client Configuration

Add to your MCP client config (e.g., Claude Desktop, Cursor):

```json
{
  "mcpServers": {
    "steward": {
      "command": "python3",
      "args": ["-m", "steward.mcp"],
      "cwd": "/path/to/your/workspace"
    }
  }
}
```

Or with the installed entry point:

```json
{
  "mcpServers": {
    "steward": {
      "command": "steward-mcp",
      "cwd": "/path/to/your/workspace"
    }
  }
}
```

## ACP Server Mode

Steward can run as an ACP (Agent Control Protocol) agent over stdio, providing a full-featured agent experience for ACP clients like Zed:

```bash
# Run as ACP server
python3 -m steward.acp

# Or via entry point after install
steward-acp
```

### Zed Configuration

```json
{
  "agent_servers": {
    "Steward (ACP)": {
      "command": "steward-acp",
      "args": [],
      "cwd": "/path/to/your/workspace"
    }
  }
}
```

### ACP Features

Steward's ACP implementation supports the full protocol:

| Feature | Description |
|---------|-------------|
| **Streaming** | Real-time text chunks, tool events, thoughts, and plan updates |
| **Tool Visibility** | `ToolCallStart`, `ToolCallProgress`, `ToolCallComplete`, `ToolCallFailed` events |
| **Session Management** | Persistent sessions with `list_sessions`, `fork_session`, `resume_session` |
| **Modes** | `default`, `plan`, `code-review` modes with automatic prompt prefixing |
| **MCP Passthrough** | Pass MCP server configs from client to agent |
| **Client Delegation** | Optional file read/write delegation to client |
| **Cancellation** | Graceful cancellation of in-progress operations |
| **Thought Streaming** | `AgentThoughtChunk` for model reasoning visibility |
| **Plan Updates** | `AgentPlanUpdate` when TODO lists change |

### Session Persistence

ACP sessions are automatically persisted to `~/.steward/sessions/<session_id>/acp_state.json`, including:
- Conversation history
- Model and mode settings
- Session configuration
- MCP server configs

### Configuration Parity

ACP sessions support the same configuration options as the CLI:

| Option | Description |
|--------|-------------|
| `system_prompt` | Custom system prompt |
| `custom_instructions` | Additional coding instructions |
| `max_steps` | Maximum tool execution steps |
| `timeout_ms` | Per-call timeout |
| `retries` | LLM retry count |

### Client File Delegation

If your ACP client supports file system capabilities (`readTextFile`, `writeTextFile`), Steward can delegate file operations to the client instead of accessing the filesystem directly. This is useful for sandboxed environments.

### Event Types

The ACP implementation emits the following event types:

| Event | When Emitted |
|-------|--------------|
| `AgentMessageChunk` | Streaming text response |
| `ToolCallStart` | Tool execution begins |
| `ToolCallProgress` | Tool execution status update |
| `ToolCallComplete` | Tool execution succeeded |
| `ToolCallFailed` | Tool execution failed |
| `AgentThoughtChunk` | Model reasoning/thinking |
| `AgentPlanUpdate` | TODO list changes |

## MCP Client Mode

Steward can also consume tools from external MCP servers. Configure servers in `.steward/mcp.json`, `mcp.json`, or `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/dir"]
    },
    "github": {
      "command": "npx", 
      "args": ["-y", "@anthropic/mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "your-token"
      }
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `mcp_list_servers` | Show configured servers |
| `mcp_list_tools` | Discover tools from a server |
| `mcp_call` | Invoke a tool on a server |
