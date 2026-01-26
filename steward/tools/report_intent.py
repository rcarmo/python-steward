"""report_intent tool - report agent's current intent."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "report_intent",
    "description": "Report the agent's current intent or action. Used to communicate what the agent is doing.",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "A short description of current intent (4 words max, gerund form). E.g., 'Exploring codebase', 'Creating parser tests'.",
            },
        },
        "required": ["intent"],
    },
}

# Store current intent for UI display
_current_intent: str = ""


def get_current_intent() -> str:
    """Get the current reported intent."""
    return _current_intent


def tool_handler(args: Dict) -> ToolResult:
    global _current_intent

    intent = args.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        raise ValueError("'intent' is required and must be non-empty")

    _current_intent = intent.strip()

    return {"id": "report_intent", "output": f"Intent: {_current_intent}"}
