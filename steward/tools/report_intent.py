"""report_intent tool - report agent's current intent."""

from __future__ import annotations

from ..types import ToolResult

# Store current intent for UI display
_current_intent: str = ""


def get_current_intent() -> str:
    """Get the current reported intent."""
    return _current_intent


def tool_report_intent(intent: str) -> ToolResult:
    """Report current task intent.

    Args:
        intent: Short description of current intent (4 words max, gerund form)
    """
    global _current_intent

    if not intent or not intent.strip():
        return {
            "id": "report_intent",
            "output": "Error: 'intent' is required and must be a non-empty string",
            "error": True,
        }

    _current_intent = intent.strip()

    return {"id": "report_intent", "output": f"Intent: {_current_intent}"}
