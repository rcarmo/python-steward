"""LLM client implementations."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from openai import AsyncOpenAI

from .types import LLMClient, LLMResult, Message, StreamHandler, ToolCallDescriptor, ToolDefinition, UsageStats

# Async stream handler type
AsyncStreamHandler = Callable[[str, bool], Awaitable[None]]


class EchoClient:
    def __init__(self, model: str) -> None:
        self.model = model

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[Union[StreamHandler, AsyncStreamHandler]] = None,
        previous_response_id: Optional[str] = None,  # noqa: ARG002
    ) -> LLMResult:  # noqa: ARG002
        last_user = next((msg for msg in reversed(messages) if msg.get("role") == "user"), None)
        content = f"Echo: {last_user.get('content', '')}" if last_user else "Echo"
        if stream_handler:
            result = stream_handler(content, True)
            if hasattr(result, "__await__"):
                await result
        return {"content": content, "response_id": "echo-123"}


class OpenAIClient:
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, default_query: Optional[Dict[str, str]] = None, timeout_ms: Optional[int] = None, use_responses_api: bool = False) -> None:
        if not api_key:
            raise ValueError("STEWARD_OPENAI_API_KEY (or Azure key) is required for this provider")
        self.model = model
        self.use_responses_api = use_responses_api
        timeout = timeout_ms / 1000.0 if timeout_ms else None
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_query=default_query, timeout=timeout)

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[Union[StreamHandler, AsyncStreamHandler]] = None,
        previous_response_id: Optional[str] = None,
    ) -> LLMResult:
        # Use Responses API if enabled and we have a previous_response_id or want to start a chain
        if self.use_responses_api:
            return await self._generate_responses_api(messages, tools, stream_handler, previous_response_id)
        return await self._generate_chat_completions(messages, tools, stream_handler)

    async def _generate_responses_api(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[Union[StreamHandler, AsyncStreamHandler]] = None,
        previous_response_id: Optional[str] = None,
    ) -> LLMResult:
        """Generate using the Responses API with conversation chaining."""
        # Extract system/developer instructions and user input
        instructions = None
        user_input = None
        for msg in messages:
            if msg.get("role") in ("system", "developer"):
                instructions = msg.get("content")
            elif msg.get("role") == "user":
                user_input = msg.get("content")

        if not user_input:
            user_input = ""

        # Build request kwargs
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": user_input,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id
        if tools:
            kwargs["tools"] = [_to_responses_tool(t) for t in tools]

        # Call Responses API
        response = await self.client.responses.create(**kwargs)

        # Extract response content and tool calls
        content = getattr(response, "output_text", None)
        response_id = getattr(response, "id", None)

        # Handle streaming callback
        if stream_handler and content:
            result = stream_handler(content, True)
            if hasattr(result, "__await__"):
                await result

        # Extract tool calls from response output
        tool_calls = _extract_responses_tool_calls(response)

        # Extract usage
        usage = _extract_usage(response)

        return {
            "content": content,
            "toolCalls": tool_calls,
            "usage": usage,
            "response_id": response_id,
        }

    async def _generate_chat_completions(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[Union[StreamHandler, AsyncStreamHandler]] = None,
    ) -> LLMResult:
        """Generate using the Chat Completions API."""
        if stream_handler:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=_to_openai_messages(messages),
                tools=[_to_openai_tool(tool) for tool in tools] if tools else None,
                tool_choice="auto" if tools else None,
                stream=True,
            )
            # Handle both awaitable (real API) and direct async iterator (tests)
            if hasattr(stream, "__aiter__"):
                async_stream = stream
            else:
                async_stream = await stream
            content_parts: List[str] = []
            # Accumulate tool calls: {index: {id, name, arguments_parts}}
            tool_call_accum: Dict[int, Dict[str, Any]] = {}
            async for event in async_stream:
                choices = getattr(event, "choices", None) or []
                if not choices:
                    continue
                choice = choices[0]
                delta = getattr(choice, "delta", None)
                if not delta:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    content_parts.append(content)
                    result = stream_handler(content, False)
                    if hasattr(result, "__await__"):
                        await result
                # Accumulate tool call chunks
                delta_tool_calls = getattr(delta, "tool_calls", None)
                if delta_tool_calls:
                    for tc in delta_tool_calls:
                        idx = getattr(tc, "index", 0)
                        if idx not in tool_call_accum:
                            tool_call_accum[idx] = {"id": "", "name": "", "arguments": ""}
                        if getattr(tc, "id", None):
                            tool_call_accum[idx]["id"] = tc.id
                        func = getattr(tc, "function", None)
                        if func:
                            if getattr(func, "name", None):
                                tool_call_accum[idx]["name"] = func.name
                            if getattr(func, "arguments", None):
                                tool_call_accum[idx]["arguments"] += func.arguments
            final_content = "".join(content_parts) if content_parts else None
            result = stream_handler("", True)
            if hasattr(result, "__await__"):
                await result
            # Build final tool calls from accumulated data
            tool_calls: Optional[List[ToolCallDescriptor]] = None
            if tool_call_accum:
                tool_calls = []
                for idx in sorted(tool_call_accum.keys()):
                    tc = tool_call_accum[idx]
                    if tc["id"] and tc["name"]:
                        try:
                            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except (TypeError, ValueError):
                            args = {}
                        tool_calls.append({"id": tc["id"], "name": tc["name"], "arguments": args})
            return {"content": final_content, "toolCalls": tool_calls if tool_calls else None}
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=_to_openai_messages(messages),
            tools=[_to_openai_tool(tool) for tool in tools] if tools else None,
            tool_choice="auto" if tools else None,
        )
        if not getattr(completion, "choices", None):
            return {"content": None, "toolCalls": None}
        choice = completion.choices[0].message
        tool_calls = _to_tool_calls(choice.tool_calls)
        content = choice.content if isinstance(choice.content, str) else None

        # Extract usage statistics including cache info
        usage = _extract_usage(completion)
        return {"content": content, "toolCalls": tool_calls, "usage": usage}


def build_client(provider: str, model: str, timeout_ms: Optional[int] = None, use_responses_api: bool = False) -> LLMClient:
    from os import getenv

    # Check env var for Responses API preference
    if getenv("STEWARD_USE_RESPONSES_API", "").lower() in ("1", "true", "yes"):
        use_responses_api = True

    if provider == "openai":
        api_key = getenv("STEWARD_OPENAI_API_KEY") or getenv("OPENAI_API_KEY") or ""
        base_url = getenv("STEWARD_OPENAI_BASE_URL") or getenv("OPENAI_BASE_URL")
        return OpenAIClient(model, api_key, base_url=base_url, timeout_ms=timeout_ms, use_responses_api=use_responses_api)
    if provider == "azure":
        endpoint = getenv("STEWARD_AZURE_OPENAI_ENDPOINT") or getenv("AZURE_OPENAI_ENDPOINT")
        api_key = getenv("STEWARD_AZURE_OPENAI_KEY") or getenv("AZURE_OPENAI_KEY")
        deployment = getenv("STEWARD_AZURE_OPENAI_DEPLOYMENT") or getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = getenv("STEWARD_AZURE_OPENAI_API_VERSION") or getenv("AZURE_OPENAI_API_VERSION") or "2024-10-01-preview"
        if not endpoint or not api_key or not deployment:
            raise ValueError("Azure provider requires endpoint, key, and deployment (STEWARD_AZURE_OPENAI_ENDPOINT/KEY/DEPLOYMENT)")
        base_url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        return OpenAIClient(model, api_key, base_url=base_url, default_query={"api-version": api_version}, timeout_ms=timeout_ms, use_responses_api=use_responses_api)
    return EchoClient(model)


def _to_openai_messages(messages: List[Message]) -> List[Dict[str, Any]]:
    converted: List[Dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Filter out invalid tool calls (missing id or name)
            valid_calls = [
                {
                    "id": call["id"] or "",
                    "type": "function",
                    "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])}
                }
                for call in msg.get("tool_calls", [])
                if call.get("id") and call.get("name")
            ]
            converted.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": valid_calls,
                }
            )
        elif msg.get("role") == "tool":
            converted.append(
                {
                    "role": "tool",
                    "content": msg.get("content") or "",
                    "tool_call_id": msg.get("tool_call_id") or "",
                }
            )
        else:
            converted.append({"role": msg["role"], "content": msg.get("content") or ""})
    return converted


def _to_openai_tool(tool: ToolDefinition) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
        },
    }


def _to_tool_calls(calls: Any) -> Optional[List[ToolCallDescriptor]]:
    if not calls:
        return None
    results: List[ToolCallDescriptor] = []
    for call in calls:
        # Skip invalid tool calls (missing id or function name)
        if not getattr(call, "id", None) or not getattr(call, "function", None):
            continue
        if not getattr(call.function, "name", None):
            continue
        try:
            args = json.loads(call.function.arguments)
        except (TypeError, ValueError):
            args = {}
        results.append({"id": call.id, "name": call.function.name, "arguments": args})
    return results if results else None


def _extract_usage(completion: Any) -> Optional[UsageStats]:
    """Extract usage statistics from API response, including prompt cache info."""
    usage = getattr(completion, "usage", None)
    if not usage:
        return None

    stats: UsageStats = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
    }

    # Extract cached tokens from prompt_tokens_details (OpenAI cache feature)
    details = getattr(usage, "prompt_tokens_details", None)
    if details:
        cached = getattr(details, "cached_tokens", 0)
        if cached:
            stats["cached_tokens"] = cached

    return stats


def _to_responses_tool(tool: ToolDefinition) -> Dict[str, Any]:
    """Convert tool definition to Responses API format."""
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
    }


def _extract_responses_tool_calls(response: Any) -> Optional[List[ToolCallDescriptor]]:
    """Extract tool calls from a Responses API response."""
    output = getattr(response, "output", None)
    if not output:
        return None

    results: List[ToolCallDescriptor] = []
    # Responses API returns output as a list of items
    if isinstance(output, list):
        for item in output:
            item_type = getattr(item, "type", None)
            if item_type == "function_call":
                call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
                name = getattr(item, "name", "")
                args_str = getattr(item, "arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except (TypeError, ValueError):
                    args = {}
                if name:
                    results.append({"id": call_id, "name": name, "arguments": args})

    return results if results else None
