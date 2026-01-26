"""report_intent tool - report agent's current intent."""
from __future__ import annotations

from typing import Dict

from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "report_intent",
    "description": "Report current task intent. REQUIRED: intent (string, 4 words max, gerund form like 'Exploring codebase').",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "REQUIRED. Short description of current intent (4 words max, gerund form). Example: 'Exploring codebase', 'Creating parser tests'.",
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
        return {"id": "report_intent", "output": "Error: 'intent' is required and must be a non-empty string", "error": True}

    _current_intent = intent.strip()

    return {"id": "report_intent", "output": f"Intent: {_current_intent}"}
