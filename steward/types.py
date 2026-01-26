"""Typed structures used across the steward runtime."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, TypedDict

Role = Literal["system", "user", "assistant", "tool"]


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


class LLMResult(TypedDict, total=False):
    content: Optional[str]
    toolCalls: Optional[List[ToolCallDescriptor]]


class LLMClient(Protocol):
    def generate(self, messages: List[Message], tools: Optional[List[ToolDefinition]] = None) -> LLMResult:
        ...


ToolHandler = Callable[[Dict[str, Any]], ToolResult]
