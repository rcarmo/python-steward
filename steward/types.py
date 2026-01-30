"""Typed structures used across the steward runtime."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Protocol, TypedDict, Union

Role = Literal["system", "developer", "user", "assistant", "tool"]


class ToolCallDescriptor(TypedDict):
    id: str
    name: str
    arguments: Dict[str, Any]


class Message(TypedDict, total=False):
    role: Role
    content: Optional[str]
    name: Optional[str]
    tool_call_id: Optional[str]
    tool_calls: Optional[List[ToolCallDescriptor]]


class ToolDefinition(TypedDict):
    name: str
    description: str
    parameters: Dict[str, Any]


class ToolResult(TypedDict, total=False):
    id: str
    output: str
    error: bool
    # Meta-tool fields: if present, runner will synthesize via LLM
    meta_prompt: str  # Prompt template for LLM synthesis
    meta_context: str  # Context data to include in synthesis
    # Next tool suggestions for umcp-style workflow hints
    next_tool: List[str]  # Recommended tools to call next


class UsageStats(TypedDict, total=False):
    """Token usage statistics from LLM API response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int  # Tokens served from prompt cache (cost reduction)


class LLMResult(TypedDict, total=False):
    content: Optional[str]
    toolCalls: Optional[List[ToolCallDescriptor]]
    usage: Optional[UsageStats]  # Token usage including cache stats
    response_id: Optional[str]  # For Responses API: chain conversations with previous_response_id


StreamHandler = Callable[[str, bool], None]
AsyncStreamHandler = Callable[[str, bool], Awaitable[None]]


class LLMClient(Protocol):
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream_handler: Optional[Union[StreamHandler, AsyncStreamHandler]] = None,
        previous_response_id: Optional[str] = None,  # For Responses API conversation chaining
    ) -> LLMResult: ...


# Tool handlers can be sync or async
ToolHandler = Callable[[Dict[str, Any]], ToolResult]
AsyncToolHandler = Callable[[Dict[str, Any]], Awaitable[ToolResult]]
