"""LLM client implementations."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .types import LLMClient, LLMResult, Message, StreamHandler, ToolCallDescriptor, ToolDefinition


class EchoClient:
    def __init__(self, model: str) -> None:
        self.model = model

    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[StreamHandler] = None,
    ) -> LLMResult:  # noqa: ARG002
        last_user = next((msg for msg in reversed(messages) if msg.get("role") == "user"), None)
        content = f"Echo: {last_user.get('content', '')}" if last_user else "Echo"
        if stream_handler:
            stream_handler(content, True)
        return {"content": content}


class OpenAIClient:
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, default_query: Optional[Dict[str, str]] = None, timeout_ms: Optional[int] = None) -> None:
        if not api_key:
            raise ValueError("STEWARD_OPENAI_API_KEY (or Azure key) is required for this provider")
        self.model = model
        timeout = timeout_ms / 1000.0 if timeout_ms else None
        self.client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query, timeout=timeout)

    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[StreamHandler] = None,
    ) -> LLMResult:
        if stream_handler:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=_to_openai_messages(messages),
                tools=[_to_openai_tool(tool) for tool in tools] if tools else None,
                tool_choice="auto" if tools else None,
                stream=True,
            )
            content_parts: List[str] = []
            tool_calls: Optional[List[ToolCallDescriptor]] = None
            for event in stream:
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
                    stream_handler(content, False)
                if getattr(delta, "tool_calls", None):
                    tool_calls = _to_tool_calls(delta.tool_calls) or tool_calls
            final_content = "".join(content_parts) if content_parts else None
            stream_handler("", True)
            return {"content": final_content, "toolCalls": tool_calls}
        completion = self.client.chat.completions.create(
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
        return {"content": content, "toolCalls": tool_calls}


def build_client(provider: str, model: str, timeout_ms: Optional[int] = None) -> LLMClient:
    from os import getenv

    if provider == "openai":
        api_key = getenv("STEWARD_OPENAI_API_KEY") or getenv("OPENAI_API_KEY") or ""
        base_url = getenv("STEWARD_OPENAI_BASE_URL") or getenv("OPENAI_BASE_URL")
        return OpenAIClient(model, api_key, base_url=base_url, timeout_ms=timeout_ms)
    if provider == "azure":
        endpoint = getenv("STEWARD_AZURE_OPENAI_ENDPOINT") or getenv("AZURE_OPENAI_ENDPOINT")
        api_key = getenv("STEWARD_AZURE_OPENAI_KEY") or getenv("AZURE_OPENAI_KEY")
        deployment = getenv("STEWARD_AZURE_OPENAI_DEPLOYMENT") or getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = getenv("STEWARD_AZURE_OPENAI_API_VERSION") or getenv("AZURE_OPENAI_API_VERSION") or "2024-10-01-preview"
        if not endpoint or not api_key or not deployment:
            raise ValueError("Azure provider requires endpoint, key, and deployment (STEWARD_AZURE_OPENAI_ENDPOINT/KEY/DEPLOYMENT)")
        base_url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        return OpenAIClient(model, api_key, base_url=base_url, default_query={"api-version": api_version}, timeout_ms=timeout_ms)
    return EchoClient(model)


def _to_openai_messages(messages: List[Message]) -> List[Dict[str, Any]]:
    converted: List[Dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            converted.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])}
                        }
                        for call in msg.get("tool_calls", [])
                    ],
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
        try:
            args = json.loads(call.function.arguments)
        except (TypeError, ValueError):
            args = {}
        results.append({"id": call.id, "name": call.function.name, "arguments": args})
    return results
