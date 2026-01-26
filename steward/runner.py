"""Steward orchestrator loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, detect_provider
from .llm import build_client
from .logger import HumanEntry, Logger
from .system_prompt import build_system_prompt
from .tools import discover_tools
from .types import LLMClient, LLMResult, Message, StreamHandler, ToolCallDescriptor, ToolDefinition
from .utils import safe_json


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


@dataclass
class RunnerResult:
    """Result from run_steward including conversation history for continuation."""
    response: Optional[str]
    messages: List[Message]  # Full conversation history


PLAN_MODE_PREFIX = "[[PLAN]]"


def run_steward(options: RunnerOptions) -> Optional[str]:
    """Run steward and return final response text. For conversation history, use run_steward_with_history."""
    result = run_steward_with_history(options)
    return result.response


def run_steward_with_history(options: RunnerOptions) -> RunnerResult:
    """Run steward and return result with full conversation history for multi-turn conversations."""
    from .conversation import DEFAULT_MAX_HISTORY_TOKENS, should_truncate, truncate_history
    from .session import get_session_context, init_session
    from .skills import get_registry

    tool_definitions, tool_handlers = discover_tools()
    provider = options.provider or detect_provider()
    model = options.model or DEFAULT_MODEL
    client = build_client(provider, model, timeout_ms=options.request_timeout_ms)
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
            logger.human(HumanEntry(title="skills", body=f"Discovered {skill_count} skill(s)", variant="tool"))

    # Detect plan mode from prompt prefix
    prompt = options.prompt
    plan_mode = prompt.startswith(PLAN_MODE_PREFIX)
    if plan_mode:
        prompt = prompt[len(PLAN_MODE_PREFIX):].strip()

    # Initialize session if requested
    session_context = None
    if options.session_id:
        init_session(options.session_id)
        session_context = get_session_context(options.session_id)

    # Use existing conversation history or start fresh
    if options.conversation_history:
        messages = list(options.conversation_history)  # Copy to avoid mutation
        messages.append({"role": "user", "content": prompt})

        # Check if we need to truncate history
        if should_truncate(messages, max_history_tokens, model):
            messages, dropped = truncate_history(messages, max_history_tokens, model)
            if dropped > 0:
                logger.human(HumanEntry(
                    title="history",
                    body=f"Truncated {dropped} tokens from conversation history",
                    variant="warn"
                ))
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
        messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": prompt})

    limit = options.max_steps or DEFAULT_MAX_STEPS
    retry_limit = options.retries or 0

    for step in range(limit):
        try:
            response = call_model_with_policies(
                client=client,
                messages=messages,
                retry_limit=retry_limit,
                logger=logger,
                tools=tool_definitions,
                stream_handler=options.stream_handler,
            )
        except Exception as err:  # noqa: BLE001
            message = str(err)
            logger.human(HumanEntry(title="model", body=f"step {step} failed: {message}", variant="error"))
            logger.json({"type": "model_error", "step": step, "error": message, "fatal": True})
            return RunnerResult(response=None, messages=messages)

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

        tool_calls = response.get("toolCalls") or []
        if tool_calls:
            content = (response.get("content") or "").strip()
            thought = format_tool_calls(tool_calls) if content in {"model"} or (content and "args=" in content) else content
            if thought and not options.stream_handler:
                logger.human(HumanEntry(title="model", body=thought, variant="model"))
            logger.human(
                HumanEntry(
                    title="model",
                    body=f"step {step} → tool calls: {', '.join(call['name'] for call in tool_calls)}",
                    variant="model",
                )
            )
            messages.append({"role": "assistant", "content": response.get("content"), "tool_calls": tool_calls})
            for call in tool_calls:
                handler = tool_handlers.get(call["name"])
                todo_variant = "todo" if call["name"] == "manage_todo_list" else "tool"
                arg_body = summarize_plan_args(call) or f"args={safe_json(call['arguments'])}"
                logger.human(HumanEntry(title=call["name"], body=arg_body, variant=todo_variant))
                if not handler:
                    messages.append({"role": "tool", "content": f"Unknown tool {call['name']}", "tool_call_id": call["id"]})
                    continue
                try:
                    result = handler(call["arguments"])
                    # Handle meta-tool: if result contains meta_prompt, synthesize via LLM
                    if result.get("meta_prompt"):
                        synthesized = synthesize_meta_tool(client, result, logger)
                        result = {"id": result.get("id", call["name"]), "output": synthesized}
                    logger.human(HumanEntry(title=call["name"], body=result.get("output", ""), variant=todo_variant))
                    logger.json(
                        {
                            "type": "tool_result",
                            "step": step,
                            "tool": call["name"],
                            "arguments": call["arguments"],
                            "output": result.get("output"),
                            "error": result.get("error") is True,
                        }
                    )
                    messages.append({"role": "tool", "content": result.get("output"), "tool_call_id": call["id"]})
                except Exception as err:  # noqa: BLE001
                    error_msg = str(err)
                    logger.human(HumanEntry(title=call["name"], body=f"error: {error_msg}", variant="error"))
                    logger.json(
                        {
                            "type": "tool_error",
                            "step": step,
                            "tool": call["name"],
                            "arguments": call["arguments"],
                            "error": error_msg,
                        }
                    )
                    messages.append({"role": "tool", "content": f"error: {error_msg}", "tool_call_id": call["id"]})
            continue

        if response.get("content"):
            if not options.stream_handler:
                logger.human(HumanEntry(title="model", body=response.get("content"), variant="model"))
            messages.append({"role": "assistant", "content": response.get("content")})
            return RunnerResult(response=response.get("content"), messages=messages)

    print("Reached max steps without final response")
    return RunnerResult(response=None, messages=messages)


def call_model_with_policies(
    *,
    client: LLMClient,
    messages: List[Message],
    retry_limit: int,
    logger: Logger,
    tools: List[ToolDefinition],
    stream_handler: Optional[StreamHandler] = None,
) -> LLMResult:
    stop_spinner = logger.start_spinner()
    try:
        attempts = max(0, retry_limit) + 1
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                result = client.generate(messages, tools, stream_handler=stream_handler)
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


def synthesize_meta_tool(client: LLMClient, result: dict, logger: Logger) -> str:
    """Synthesize a response from a meta-tool using the LLM."""
    meta_prompt = result.get("meta_prompt", "")
    logger.human(HumanEntry(title="meta-tool", body="synthesizing response...", variant="tool"))
    synthesis_messages: List[Message] = [
        {"role": "system", "content": "You are a helpful assistant that synthesizes information from search results into clear, cited answers."},
        {"role": "user", "content": meta_prompt},
    ]
    stop_spinner = logger.start_spinner()
    try:
        synthesis_result = client.generate(synthesis_messages, tools=None)
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
            lines.append(f"- **{skill.name}** ({skill.path}): {skill.description[:100]}")
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
