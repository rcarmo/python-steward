# Steward (Python)

![Steward Logo](docs/steward-256.png)

Steward is a Python CLI harness for running LLMs with a Copilot-style toolset. It is developed primarily against Azure OpenAI but also supports OpenAI-compatible hosts and a local echo provider, and was in itself bootstrapped by a [`bun` version](https://github.com/rcarmo/bun-steward).

## Quick start

1) Install:

```bash
python3 -m pip install -e .
```

2) Run (echo provider, default):

```bash
python3 -m steward.cli "List files in the workspace"
```

3) Run with Azure (set your env vars, options first):

```bash
STEWARD_AZURE_OPENAI_ENDPOINT=... \
STEWARD_AZURE_OPENAI_KEY=... \
STEWARD_AZURE_OPENAI_DEPLOYMENT=... \
python3 -m steward.cli --provider azure --model gpt-4o-mini "Read README and summarize"
```

4) Optional sandbox (auto mkdir + chdir):

```bash
python3 -m steward.cli --sandbox sandbox --provider azure --model gpt-4o-mini "List files"
```

## CLI options (`python -m steward.cli`)

- `--provider <echo|openai|azure>` (default: `echo` unless overridden by `STEWARD_PROVIDER` or Makefile wrapper)
- `--model <name>` (default: `gpt-4o-mini` unless overridden by `STEWARD_MODEL` or Makefile wrapper)
- `--max-steps <n>` (default from config)
- `--timeout-ms <n>` per LLM call
- `--retries <n>` LLM retries
- `--log-json <file>` / `--no-log-json`
- `--quiet` (suppress human logs) / `--pretty` (color logs)
- `--system <file>` custom system prompt
- `--sandbox [dir]` run inside/create a sandbox directory
- `--session [id]` enable session persistence with checkpoints (auto-generates ID if not specified)
- `--instructions <file>` load custom coding instructions to inject into system prompt

You can provide your own system prompt via `--system`; no default file is bundled.

### Plan Mode

Prefix your prompt with `[[PLAN]]` to enter plan mode, which instructs the agent to:
- Analyze the codebase and create a structured implementation plan
- Save the plan to the session's `plan.md` file
- Wait for explicit approval before implementing

```bash
python3 -m steward.cli --session "[[PLAN]] Add user authentication to the API"
```

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

Then use the MCP tools:
- `mcp_list_servers` - Show configured servers
- `mcp_list_tools` - Discover tools from a server
- `mcp_call` - Invoke a tool on a server

## Tools (Python implementation)

### File Operations

| Tool | Description |
| --- | --- |
| `view` | View file contents with line numbers, or list directory entries (2 levels deep). Supports `view_range` for partial file reads. |
| `grep` | Ripgrep-style content search with `output_mode` (content/files_with_matches/count), `glob` filter, context flags (`-A`, `-B`, `-C`), `-i` case-insensitive, `-n` line numbers. |
| `glob` | Fast file pattern matching (e.g., `**/*.ts`, `*.{js,jsx}`). |
| `create` | Create new file with content; fails if file exists; auto-creates parent directories. |
| `edit` | String replacement in files; replaces exactly one occurrence of `old_str` with `new_str`. |
| `mkdir` | Create directory with automatic parent directory creation. |
| `apply_patch` | Apply unified diffs with validation. |
| `replace_string_in_file` / `multi_replace_string_in_file` | Alternative string replacement tools. |

### Shell & Process Management

| Tool | Description |
| --- | --- |
| `bash` | Shell execution with `mode` (sync/async), `initial_wait`, `detach` for persistent processes. Gated by `STEWARD_ALLOW_EXECUTE=1`. |
| `write_bash` | Send input to async bash sessions; supports special keys (`{enter}`, `{up}`, `{down}`, etc.). |
| `read_bash` | Read output from async bash sessions. |
| `stop_bash` | Terminate async bash sessions. |
| `list_bash` | List all active async bash sessions. |

### Task & Memory Management

| Tool | Description |
| --- | --- |
| `update_todo` | Markdown checklist for task tracking; persisted to `.steward-todo.md`. |
| `store_memory` | Persist facts about codebase for future tasks; stored in `.steward-memory.json`. |
| `report_intent` | Report current agent intent for UI status updates. |
| `ask_user` | Ask user questions with optional multiple choice responses. |

### Web & Search

| Tool | Description |
| --- | --- |
| `web_fetch` | Fetch URL as markdown or raw HTML; pagination via `start_index`; `max_length` cap (default 5000, max 20000). |
| `web_search` | Web search with LLM synthesis and citations (meta-tool pattern). |

### Git Operations

| Tool | Description |
| --- | --- |
| `git_status` / `git_diff` / `git_commit` / `git_stash` | Git helpers for workspace/subpaths. |

### Development Environment

| Tool | Description |
| --- | --- |
| `run_js` | QuickJS sandbox; execute code or load from workspace path; timeout/output caps; optional `allowNetwork` fetch helper. |
| `configure_python_environment` / `get_python_executable_details` / `install_python_packages` | Python env info/selection/install helpers. |

### Code Analysis

| Tool | Description |
| --- | --- |
| `list_code_usages` | ripgrep-based symbol finder. |
| `get_changed_files` | Git status summary grouped by state. |
| `workspace_summary` | Summarize top-level files/dirs and package metadata if present. |

### Skills & MCP

| Tool | Description |
| --- | --- |
| `discover_skills` | Find all SKILL.md files in the workspace. |
| `load_skill` | Load and parse a SKILL.md file to understand tool/agent capabilities. |
| `mcp_list_servers` | List configured MCP servers from mcp.json. |
| `mcp_list_tools` | List available tools from an MCP server. |
| `mcp_call` | Invoke a tool on an MCP server. |

## Default system prompt

The default system prompt includes:
- Tone and style guidance (concise, direct responses)
- Parallel tool calling instructions for efficiency
- Tool-specific usage guidance
- Code change rules (minimal modifications, run tests)
- Security and privacy constraints
- Session and plan mode support
- Environment context (CWD, git root)

Custom instructions can be injected via `--instructions <file>`.

## Providers

- Echo: `--provider echo` (no credentials)
- OpenAI-compatible: `--provider openai` with `STEWARD_OPENAI_API_KEY`/`OPENAI_API_KEY` and optional `STEWARD_OPENAI_BASE_URL`
- Azure OpenAI: `--provider azure` with `STEWARD_AZURE_OPENAI_ENDPOINT`, `STEWARD_AZURE_OPENAI_KEY`, `STEWARD_AZURE_OPENAI_DEPLOYMENT`, optional `STEWARD_AZURE_OPENAI_API_VERSION` (default 2024-10-01-preview)

## Notes

- Path access is constrained to the current working directory (or sandbox when provided).
- The run loop stops after max steps even if the model keeps calling tools.
- `bash` is gated by `STEWARD_ALLOW_EXECUTE=1` and supports allow/deny lists, timeouts, and audit logging.

## Make targets

- `make install` — pip install -e .
- `make test` — python -m pytest tests
- `make scenario` — sample run in current workspace (uses provider/model defaults)
- `make inception` — sample run inside sandbox/ using `--sandbox`

## Roadmap

- [ ] Improve logging ergonomics
- [x] Add MCP support (stdio transport)
- [x] Add interactive shell I/O tools
- [x] Add session management and plan mode
- [x] Add REPL
- [ ] Add streaming support
- [ ] Add sub-agent orchestration
- [ ] Additional provider shims as needed
