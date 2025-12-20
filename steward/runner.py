"""Steward orchestrator loop."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, DEFAULT_PROVIDER
from .llm import build_client
from .logger import HumanEntry, Logger
from .tools import discover_tools
from .types import LLMClient, LLMResult, Message, ToolCallDescriptor, ToolDefinition
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


def run_steward(options: RunnerOptions) -> Optional[str]:
    tool_definitions, tool_handlers = discover_tools()
    client = build_client(options.provider or DEFAULT_PROVIDER, options.model or DEFAULT_MODEL, timeout_ms=options.request_timeout_ms)
    logger = Logger(
        provider=options.provider or DEFAULT_PROVIDER,
        model=options.model or DEFAULT_MODEL,
        log_json_path=options.log_json_path,
        enable_human_logs=options.enable_human_logs,
        enable_file_logs=options.enable_file_logs,
        pretty=options.pretty_logs,
    )

    messages: List[Message] = []
    system_text = options.system_prompt or default_system_prompt([tool["name"] for tool in tool_definitions])
    messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": options.prompt})

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
            )
        except Exception as err:  # noqa: BLE001
            message = str(err)
            logger.human(HumanEntry(title="model", body=f"step {step} failed: {message}", variant="error"))
            logger.json({"type": "model_error", "step": step, "error": message, "fatal": True})
            return None

        logger.json(
            {
                "type": "model_response",
                "step": step,
                "provider": options.provider or DEFAULT_PROVIDER,
                "model": options.model or DEFAULT_MODEL,
                "content": response.get("content"),
                "toolCalls": response.get("toolCalls"),
            }
        )

        tool_calls = response.get("toolCalls") or []
        if tool_calls:
            content = (response.get("content") or "").strip()
            thought = format_tool_calls(tool_calls) if content in {"model"} or (content and "args=" in content) else content
            if thought:
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
            logger.human(HumanEntry(title="model", body=response.get("content"), variant="model"))
            return response.get("content")

    print("Reached max steps without final response")
    return None


def call_model_with_policies(
    *,
    client: LLMClient,
    messages: List[Message],
    retry_limit: int,
    logger: Logger,
    tools: List[ToolDefinition],
) -> LLMResult:
    stop_spinner = logger.start_spinner()
    try:
        attempts = max(0, retry_limit) + 1
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                result = client.generate(messages, tools)
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


def default_system_prompt(tool_names: List[str]) -> str:
    tools = ", ".join(tool_names)
    return "\n".join(
        [
            "You are GitHub Copilot running in a local CLI environment.",
            f"Tools: {tools}.",
            "Stay within the current workspace; do not invent files or paths.",
            "Briefly state your intent before calling tools; narrate what you are doing and why.",
            "When multiple actions are needed, manage the conversation plan via manage_todo_list: send the full todoList (id/title/description/status) each time and let the tool persist it to .steward-plan.json.",
            "Use tools to gather context before editing. Keep replies short and task-focused.",
            "After tools finish, give a concise result and, if helpful, next steps.",
        ]
    )


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
