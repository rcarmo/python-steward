"""Steward orchestrator loop."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, PLAN_MODE_PREFIX, detect_provider, get_system_role
from .llm import build_client
from .logger import HumanEntry, Logger
from .system_prompt import build_system_prompt
from .tools import discover_tools
from .types import (
    LLMClient,
    LLMResult,
    Message,
    StreamHandler,
    ToolCallDescriptor,
    ToolDefinition,
    ToolResult,
    UsageStats,
)
from .utils import safe_json

# Import ACP event types (optional dependency)
try:
    from .acp_events import AcpEventQueue, CancellationToken, is_dangerous_tool
except ImportError:
    AcpEventQueue = None  # type: ignore
    CancellationToken = None  # type: ignore

    def is_dangerous_tool(name: str) -> bool:  # type: ignore
        return False


@dataclass
class RunnerOptions:
    prompt: str
    system_prompt: Optional[str] = None
    max_steps: Optional[int] = None
    request_timeout_ms: Optional[int] = None
    retries: Optional[int] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    log_json_path: Optional[str] = None
    enable_human_logs: bool = True
    enable_file_logs: bool = True
    pretty_logs: bool = True
    compact_logs: bool = False  # Abbreviated single-line logging for REPL
    session_id: Optional[str] = None
    custom_instructions: Optional[str] = None
    conversation_history: Optional[List[Message]] = None  # For multi-turn conversations
    max_history_tokens: Optional[int] = None  # Token limit for conversation history
    stream_handler: Optional[StreamHandler] = None
    previous_response_id: Optional[str] = None  # For Responses API conversation chaining
    llm_client: Optional[LLMClient] = None  # Reuse client/session across calls
    # ACP integration
    event_queue: Optional["AcpEventQueue"] = None  # Event queue for ACP streaming updates
    cancellation_token: Optional["CancellationToken"] = None  # For cancellation support
    require_permission: bool = False  # Whether to request permission for dangerous tools


@dataclass
class RunnerResult:
    """Result from run_steward including conversation history for continuation."""

    response: Optional[str]
    messages: List[Message]  # Full conversation history
    last_response_id: Optional[str] = None  # For Responses API conversation chaining
    usage_summary: Optional[UsageStats] = None  # Aggregated token/cache stats for session summary



def run_steward(options: RunnerOptions) -> Optional[str]:
    """Run steward and return final response text. For conversation history, use run_steward_with_history."""
    result = run_steward_with_history(options)
    return result.response


def run_steward_with_history(options: RunnerOptions) -> RunnerResult:
    """Run steward synchronously (wraps async version)."""
    return asyncio.run(run_steward_async(options))


async def run_steward_async(options: RunnerOptions) -> RunnerResult:
    """Run steward and return result with full conversation history for multi-turn conversations."""
    from .conversation import DEFAULT_MAX_HISTORY_TOKENS, compact_history, should_truncate, truncate_history
    from .session import get_session_context, init_session
    from .skills import get_registry

    tool_definitions, tool_handlers = discover_tools()
    provider = options.provider or detect_provider()
    model = options.model or DEFAULT_MODEL
    client = options.llm_client or build_client(provider, model, timeout_ms=options.request_timeout_ms)
    logger = Logger(
        provider=provider,
        model=model,
        log_json_path=options.log_json_path,
        enable_human_logs=options.enable_human_logs,
        enable_file_logs=options.enable_file_logs,
        pretty=options.pretty_logs,
        compact=options.compact_logs,
    )

    max_history_tokens = options.max_history_tokens or DEFAULT_MAX_HISTORY_TOKENS

    # Auto-discover skills at startup
    registry = get_registry()
    if not registry.is_discovered:
        skill_count = registry.discover()
        if skill_count > 0:
            skill_names = [s.name for s in registry.all()]
            logger.human(
                HumanEntry(
                    title="skills", body=f"Discovered {skill_count} skill(s): {', '.join(skill_names)}", variant="tool"
                )
            )

    # Detect plan mode from prompt prefix
    prompt = options.prompt
    plan_mode = prompt.startswith(PLAN_MODE_PREFIX)
    if plan_mode:
        prompt = prompt[len(PLAN_MODE_PREFIX) :].strip()

    # Initialize session if requested
    session_context = None
    if options.session_id:
        init_session(options.session_id)
        session_context = get_session_context(options.session_id)

    # Determine the system role based on model (developer for o-series, system for others)
    system_role = get_system_role(model)

    # Use existing conversation history or start fresh
    if options.conversation_history:
        messages = list(options.conversation_history)  # Copy to avoid mutation
        messages.append({"role": "user", "content": prompt})

        # Codex-style context management: compact before truncating
        # First try compaction (summarizes old tool results)
        if should_truncate(messages, max_history_tokens, model):
            messages, summary = compact_history(messages, keep_recent_turns=5, model=model)
            if summary:
                logger.human(HumanEntry(title="history", body=f"Compacted: {summary[:80]}...", variant="tool"))

            # If still too large after compaction, truncate
            if should_truncate(messages, max_history_tokens, model):
                messages, dropped = truncate_history(messages, max_history_tokens, model)
                if dropped > 0:
                    logger.human(
                        HumanEntry(
                            title="history",
                            body=f"Truncated {dropped} tokens from conversation history",
                            variant="warn",
                        )
                    )
    else:
        # Build skill context for system prompt
        skill_context = _build_skill_context(registry, prompt)

        messages: List[Message] = []
        if options.system_prompt:
            system_text = options.system_prompt
        else:
            system_text = build_system_prompt(
                [tool["name"] for tool in tool_definitions],
                custom_instructions=options.custom_instructions,
                session_context=session_context,
                plan_mode=plan_mode,
                skill_context=skill_context,
            )
        messages.append({"role": system_role, "content": system_text})
        messages.append({"role": "user", "content": prompt})

    limit = options.max_steps or DEFAULT_MAX_STEPS
    retry_limit = options.retries or 0

    # Track response_id for Responses API conversation chaining
    last_response_id = options.previous_response_id
    usage_totals: Optional[UsageStats] = None

    # Create ACP-aware stream handler if event queue is provided
    acp_stream_handler = options.stream_handler
    if options.event_queue and not acp_stream_handler:
        async def _acp_stream_handler(chunk: str, done: bool) -> None:
            if chunk:
                await options.event_queue.emit_text_chunk(chunk)
            if done:
                await options.event_queue.emit_text_done()

        # Wrap async handler for sync interface expected by LLM client
        def _sync_acp_stream_handler(chunk: str, done: bool) -> None:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_acp_stream_handler(chunk, done))
            else:
                loop.run_until_complete(_acp_stream_handler(chunk, done))

        acp_stream_handler = _sync_acp_stream_handler

    for step in range(limit):
        # Check for cancellation at start of each step
        if options.cancellation_token and options.cancellation_token.is_cancelled:
            if options.event_queue:
                await options.event_queue.emit_error("Operation cancelled by user", fatal=True)
            return RunnerResult(response=None, messages=messages, last_response_id=last_response_id)

        try:
            response = await call_model_with_policies(
                client=client,
                messages=messages,
                retry_limit=retry_limit,
                logger=logger,
                tools=tool_definitions,
                stream_handler=acp_stream_handler,
                previous_response_id=last_response_id,
            )
        except asyncio.CancelledError:
            if options.event_queue:
                await options.event_queue.emit_error("Operation cancelled", fatal=True)
            return RunnerResult(response=None, messages=messages, last_response_id=last_response_id)
        except Exception as err:  # noqa: BLE001
            message = str(err)
            logger.human(HumanEntry(title="model", body=f"step {step} failed: {message}", variant="error"))
            logger.json({"type": "model_error", "step": step, "error": message, "fatal": True})
            if options.event_queue:
                await options.event_queue.emit_error(message, fatal=True)
            return RunnerResult(response=None, messages=messages, last_response_id=last_response_id)

        # Update response_id for next iteration (Responses API chaining)
        if response.get("response_id"):
            last_response_id = response.get("response_id")

        usage = response.get("usage")
        if usage:
            usage_totals = _merge_usage(usage_totals, usage)

        logger.json(
            {
                "type": "model_response",
                "step": step,
                "provider": provider,
                "model": model,
                "content": response.get("content"),
                "toolCalls": response.get("toolCalls"),
            }
        )

        # Log cache statistics if available (helps debug prompt caching effectiveness)
        if usage:
            cached = usage.get("cached_tokens", 0)
            prompt = usage.get("prompt_tokens", 0)
            if cached > 0 and prompt > 0:
                cache_pct = int(100 * cached / prompt)
                logger.json(
                    {"type": "cache_stats", "cached_tokens": cached, "prompt_tokens": prompt, "cache_pct": cache_pct}
                )

        tool_calls = response.get("toolCalls") or []
        # Filter out invalid tool calls (missing name)
        tool_calls = [call for call in tool_calls if call.get("name")]
        if tool_calls:
            content = (response.get("content") or "").strip()
            thought = (
                format_tool_calls(tool_calls) if content in {"model"} or (content and "args=" in content) else content
            )
            if thought and not options.stream_handler:
                logger.human(HumanEntry(title="model", body=thought, variant="model"))
            # Emit thought to event queue for streaming
            if thought and options.event_queue:
                await options.event_queue.emit_thought(thought)
            logger.human(
                HumanEntry(
                    title="model",
                    body=f"step {step} → tool calls: {', '.join(call['name'] for call in tool_calls)}",
                    variant="model",
                )
            )
            messages.append({"role": "assistant", "content": response.get("content"), "tool_calls": tool_calls})

            # Execute tool calls in parallel
            results = await execute_tools_parallel(
                tool_calls,
                tool_handlers,
                client,
                logger,
                step,
                event_queue=options.event_queue,
                cancellation_token=options.cancellation_token,
                require_permission=options.require_permission,
            )

            # Append results to messages
            for call, result in zip(tool_calls, results):
                messages.append({"role": "tool", "content": result.get("output") or "", "tool_call_id": call["id"]})

            continue

        if response.get("content"):
            if not options.stream_handler:
                logger.human(HumanEntry(title="model", body=response.get("content"), variant="model"))
            messages.append({"role": "assistant", "content": response.get("content")})
            return RunnerResult(
                response=response.get("content"),
                messages=messages,
                last_response_id=last_response_id,
                usage_summary=usage_totals,
            )

    print("Reached max steps without final response")
    return RunnerResult(response=None, messages=messages, last_response_id=last_response_id, usage_summary=usage_totals)


def _parse_todo_output(output: str) -> List[Dict[str, str]]:
    """Parse update_todo output into plan entries for ACP.

    Args:
        output: Output from update_todo tool (markdown checklist)

    Returns:
        List of plan entry dicts with content, status, priority
    """
    entries: List[Dict[str, str]] = []
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("- [x]") or line.startswith("- [X]"):
            entries.append({
                "content": line[5:].strip(),
                "status": "completed",
                "priority": "medium",
            })
        elif line.startswith("- [ ]"):
            entries.append({
                "content": line[5:].strip(),
                "status": "pending",
                "priority": "medium",
            })
    return entries


async def execute_tools_parallel(
    tool_calls: List[ToolCallDescriptor],
    tool_handlers: Dict[str, Callable],
    client: LLMClient,
    logger: Logger,
    step: int,
    event_queue: Optional["AcpEventQueue"] = None,
    cancellation_token: Optional["CancellationToken"] = None,
    require_permission: bool = False,
) -> List[ToolResult]:
    """Execute multiple tool calls in parallel using asyncio.

    Args:
        tool_calls: List of tool calls to execute
        tool_handlers: Map of tool name to handler function
        client: LLM client for meta-tool synthesis
        logger: Logger for human and JSON logs
        step: Current step number
        event_queue: Optional ACP event queue for streaming updates
        cancellation_token: Optional token for cancellation support
        require_permission: Whether to request permission for dangerous tools
    """

    async def run_one(call: ToolCallDescriptor) -> ToolResult:
        tool_name = call["name"]
        tool_call_id = call["id"]
        arguments = call["arguments"]

        # Check for cancellation before starting
        if cancellation_token and cancellation_token.is_cancelled:
            return {"id": tool_name, "output": "Operation cancelled", "error": True}

        handler = tool_handlers.get(tool_name)
        todo_variant = "todo" if tool_name == "manage_todo_list" else "tool"
        arg_body = summarize_plan_args(call) or f"args={safe_json(arguments)}"
        logger.human(HumanEntry(title=tool_name, body=arg_body, variant=todo_variant))

        if not handler:
            if event_queue:
                await event_queue.emit_tool_failed(tool_call_id, tool_name, f"Unknown tool {tool_name}")
            return {"id": tool_name, "output": f"Unknown tool {tool_name}", "error": True}

        # Emit tool start event
        if event_queue:
            await event_queue.emit_tool_start(tool_call_id, tool_name, arguments)

        # Check permission for dangerous tools
        if require_permission and event_queue and is_dangerous_tool(tool_name):
            try:
                permission = await event_queue.request_permission(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    reason=f"Tool '{tool_name}' may modify files or execute commands",
                )
                if not permission.approved:
                    await event_queue.emit_tool_failed(tool_call_id, tool_name, "Permission denied by user")
                    return {"id": tool_name, "output": "Permission denied by user", "error": True}
            except asyncio.CancelledError:
                await event_queue.emit_tool_failed(tool_call_id, tool_name, "Operation cancelled")
                return {"id": tool_name, "output": "Operation cancelled", "error": True}

        try:
            # Check if handler is async or sync
            if inspect.iscoroutinefunction(handler):
                result = await handler(arguments)
            else:
                # Run sync handler in thread pool to avoid blocking
                result = await asyncio.get_event_loop().run_in_executor(None, handler, arguments)

            # Check for cancellation after execution
            if cancellation_token and cancellation_token.is_cancelled:
                if event_queue:
                    await event_queue.emit_tool_failed(tool_call_id, tool_name, "Operation cancelled")
                return {"id": tool_name, "output": "Operation cancelled", "error": True}

            # Handle meta-tool: if result contains meta_prompt, synthesize via LLM
            if result.get("meta_prompt"):
                if event_queue:
                    await event_queue.emit_tool_progress(tool_call_id, tool_name, "in_progress", "Synthesizing response...")
                synthesized = await synthesize_meta_tool_async(client, result, logger)
                result = {"id": result.get("id", tool_name), "output": synthesized}

            output = result.get("output", "")
            logger.human(HumanEntry(title=tool_name, body=output, variant=todo_variant))
            logger.json(
                {
                    "type": "tool_result",
                    "step": step,
                    "tool": tool_name,
                    "arguments": arguments,
                    "output": output,
                    "error": result.get("error") is True,
                }
            )

            # Emit completion event
            if event_queue:
                if result.get("error"):
                    await event_queue.emit_tool_failed(tool_call_id, tool_name, output)
                else:
                    await event_queue.emit_tool_complete(tool_call_id, tool_name, output)
                    # Parse update_todo output and emit plan update
                    if tool_name == "update_todo":
                        plan_entries = _parse_todo_output(output)
                        if plan_entries:
                            await event_queue.emit_plan_update(plan_entries)

            return result
        except asyncio.CancelledError:
            if event_queue:
                await event_queue.emit_tool_failed(tool_call_id, tool_name, "Operation cancelled")
            return {"id": tool_name, "output": "Operation cancelled", "error": True}
        except Exception as err:  # noqa: BLE001
            error_msg = str(err)
            logger.human(HumanEntry(title=tool_name, body=f"error: {error_msg}", variant="error"))
            logger.json(
                {
                    "type": "tool_error",
                    "step": step,
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": error_msg,
                }
            )
            if event_queue:
                await event_queue.emit_tool_failed(tool_call_id, tool_name, error_msg)
            return {"id": tool_name, "output": f"error: {error_msg}", "error": True}

    # Run all tool calls concurrently
    return await asyncio.gather(*[run_one(call) for call in tool_calls])


async def call_model_with_policies(
    *,
    client: LLMClient,
    messages: List[Message],
    retry_limit: int,
    logger: Logger,
    tools: List[ToolDefinition],
    stream_handler: Optional[StreamHandler] = None,
    previous_response_id: Optional[str] = None,
) -> LLMResult:
    # Only show spinner if not streaming (streaming has its own UI)
    stop_spinner = logger.start_spinner() if not stream_handler else lambda: None
    try:
        attempts = max(0, retry_limit) + 1
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                result = await client.generate(
                    messages, tools, stream_handler=stream_handler, previous_response_id=previous_response_id
                )
                if attempt > 1:
                    logger.human(HumanEntry(title="model", body=f"retry {attempt} succeeded", variant="model"))
                    logger.json({"type": "model_retry_success", "attempt": attempt})
                return result
            except Exception as err:  # noqa: BLE001
                last_error = err
                is_last = attempt == attempts
                variant = "error" if is_last else "warn"
                logger.human(HumanEntry(title="model", body=f"attempt {attempt} failed: {err}", variant=variant))
                logger.json({"type": "model_retry", "attempt": attempt, "error": str(err), "terminal": is_last})
                if is_last:
                    break
        if last_error:
            raise last_error
        raise RuntimeError("Unknown model error")
    finally:
        stop_spinner()


def _merge_usage(total: Optional[UsageStats], usage: UsageStats) -> UsageStats:
    """Aggregate usage stats across multiple model calls."""
    if total is None:
        total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"):
        total[key] = total.get(key, 0) + int(usage.get(key, 0) or 0)
    return total


def format_tool_calls(calls: List[ToolCallDescriptor]) -> str:
    return ", ".join(call["name"] for call in calls)


def summarize_plan_args(call: ToolCallDescriptor) -> Optional[str]:
    if call["name"] != "manage_todo_list":
        return None
    todo_list = call["arguments"].get("todoList") if isinstance(call["arguments"], dict) else None
    if not isinstance(todo_list, list):
        return None
    ids = [item.get("id") for item in todo_list if isinstance(item, dict) and isinstance(item.get("id"), int)]
    return f"todoList size={len(todo_list)} ids={','.join(str(i) for i in ids)}"


async def synthesize_meta_tool_async(client: LLMClient, result: dict, logger: Logger) -> str:
    """Synthesize a response from a meta-tool using the LLM."""
    meta_prompt = result.get("meta_prompt", "")
    logger.human(HumanEntry(title="meta-tool", body="synthesizing response...", variant="tool"))
    synthesis_messages: List[Message] = [
        {
            "role": "system",
            "content": "You are a helpful assistant that synthesizes information from search results into clear, cited answers.",
        },
        {"role": "user", "content": meta_prompt},
    ]
    stop_spinner = logger.start_spinner()
    try:
        synthesis_result = await client.generate(synthesis_messages, tools=None)
        return synthesis_result.get("content") or "(no synthesis generated)"
    except Exception as err:
        return f"[synthesis error] {err}\n\nRaw context:\n{result.get('meta_context', '')}"
    finally:
        stop_spinner()


def _build_skill_context(registry: "SkillRegistry", prompt: str) -> Optional[str]:  # noqa: F821
    """Build skill context for system prompt based on discovered skills and prompt matching."""
    if not registry.is_discovered or not registry.all():
        return None

    # Get top matching skills for the prompt
    matches = registry.match(prompt, limit=3)

    lines = ["<skills>"]
    lines.append(f"Discovered {len(registry.all())} skill(s) in workspace.")

    if matches:
        lines.append("\nRelevant skills for this task:")
        for skill, score in matches:
            desc = (skill.description or "")[:100]
            lines.append(f"- **{skill.name}** ({skill.path}): {desc}")
            if skill.requires:
                lines.append(f"  Requires: {', '.join(skill.requires)}")
            if skill.chain:
                lines.append(f"  Chains to: {', '.join(skill.chain)}")

        lines.append("\nUse load_skill to read full instructions before starting.")
        lines.append("After completing a skill, check its 'chain' for follow-up skills.")
    else:
        lines.append("Use suggest_skills or discover_skills to find relevant skills.")

    lines.append("</skills>")
    return "\n".join(lines)
