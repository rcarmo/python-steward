# Steward (Python)

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

You can provide your own system prompt via `--system`; no default file is bundled.

## Tools (Python implementation)

| Tool | Description |
| --- | --- |
| `read_file` | File contents with optional line ranges; `maxLines`/`maxBytes` caps. |
| `grep_search` | Recursive search with include/exclude globs, context, smartCase/fixedString/wordMatch, hidden/binary toggles. |
| `create_file` | Create or overwrite a file with content. |
| `create_directory` | `mkdir` with `parents`/`existOk` flags. |
| `list_dir` | List directory entries (skips `.git`/`node_modules` unless `includeIgnored`). |
| `apply_patch` | Apply unified diffs with validation. |
| `manage_todo_list` | Copilot-style plan persisted to `.steward-plan.json`; accepts status aliases `blocked`/`done`. |
| `run_in_terminal` | Gated shell exec (`STEWARD_ALLOW_EXECUTE=1`); `cwd`/`env`/`timeout`/`background`/`stream`/output caps; allow/deny lists; audit log. |
| `run_js` | QuickJS sandbox; execute code or load from workspace path; timeout/output caps; optional `allowNetwork` fetch helper. |
| `fetch_data` / `fetch_webpage` | HTTP/data: fetch with optional `textOnly` stripping and content-type note; size caps. |
| `git_status` / `git_diff` / `git_commit` / `git_stash` | Git helpers for workspace/subpaths. |
| `file_search` | Glob listing with include/exclude filters. |
| `list_code_usages` | ripgrep-based symbol finder. |
| `get_changed_files` | Git status summary grouped by state. |
| `configure_python_environment` / `get_python_executable_details` / `install_python_packages` | Python env info/selection/install helpers. |
| `workspace_summary` | Summarize top-level files/dirs and package metadata if present. |

## Default system prompt

- Declares the current tool set above.
- Instructs the model to narrate intent before tool calls and to manage multi-step work via manage_todo_list (send full todoList each time; persisted to .steward-plan.json).
- Keeps replies concise with optional next steps.

## Providers

- Echo: `--provider echo` (no credentials)
- OpenAI-compatible: `--provider openai` with `STEWARD_OPENAI_API_KEY`/`OPENAI_API_KEY` and optional `STEWARD_OPENAI_BASE_URL`
- Azure OpenAI: `--provider azure` with `STEWARD_AZURE_OPENAI_ENDPOINT`, `STEWARD_AZURE_OPENAI_KEY`, `STEWARD_AZURE_OPENAI_DEPLOYMENT`, optional `STEWARD_AZURE_OPENAI_API_VERSION` (default 2024-10-01-preview)

## Notes

- Path access is constrained to the current working directory (or sandbox when provided).
- The run loop stops after max steps even if the model keeps calling tools.
- `run_in_terminal` is gated by `STEWARD_ALLOW_EXECUTE=1` and supports allow/deny lists, timeouts, and audit logging.

## Make targets

- `make install` — pip install -e .
- `make test` — python -m pytest tests
- `make scenario` — sample run in current workspace (uses provider/model defaults)
- `make inception` — sample run inside sandbox/ using `--sandbox`

## Roadmap

- [ ] Improve logging ergonomics
- [ ] Add MCP support (testing against [`umcp`](https://github.com/rcarmo/umcp))
- [ ] Additional provider shims as needed
