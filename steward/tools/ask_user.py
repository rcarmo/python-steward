"""ask_user tool - ask the user a question and wait for response."""
from __future__ import annotations

import json
import sys
from typing import Dict, List, Optional

from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "ask_user",
    "description": "Ask the user a question and wait for their response. Use for clarifying requirements, getting preferences, or offering choices.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user.",
            },
            "choices": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of choices for multiple choice. Prefer providing choices when possible.",
            },
            "allow_freeform": {
                "type": "boolean",
                "description": "Whether to allow freeform text input in addition to choices (default: true).",
            },
        },
        "required": ["question"],
    },
}

# Callback for getting user input (can be overridden for testing or different UIs)
_input_callback: Optional[callable] = None


def set_input_callback(callback: callable) -> None:
    """Set a custom callback for getting user input."""
    global _input_callback
    _input_callback = callback


def _default_input(question: str, choices: Optional[List[str]], allow_freeform: bool) -> str:
    """Default console-based input handler."""
    print(f"\n🤖 {question}", file=sys.stderr)

    if choices:
        print("\nChoices:", file=sys.stderr)
        for i, choice in enumerate(choices, 1):
            print(f"  {i}. {choice}", file=sys.stderr)
        if allow_freeform:
            print(f"  {len(choices) + 1}. (Enter custom response)", file=sys.stderr)

        print("\nEnter number or response: ", end="", file=sys.stderr)
        sys.stderr.flush()

        response = input().strip()

        # Check if user entered a number
        try:
            idx = int(response)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
            elif allow_freeform and idx == len(choices) + 1:
                print("Enter your response: ", end="", file=sys.stderr)
                sys.stderr.flush()
                return input().strip()
        except ValueError:
            pass

        # Return raw response if freeform allowed or invalid choice
        if allow_freeform:
            return response
        else:
            return f"Invalid choice: {response}"
    else:
        print("\nYour response: ", end="", file=sys.stderr)
        sys.stderr.flush()
        return input().strip()


def tool_handler(args: Dict) -> ToolResult:
    question = args.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("'question' is required and must be non-empty")

    choices = args.get("choices")
    if choices is not None and not isinstance(choices, list):
        raise ValueError("'choices' must be a list of strings")

    allow_freeform = args.get("allow_freeform", True)
    if not isinstance(allow_freeform, bool):
        allow_freeform = True

    # Use custom callback if set, otherwise default console input
    if _input_callback:
        response = _input_callback(question.strip(), choices, allow_freeform)
    else:
        response = _default_input(question.strip(), choices, allow_freeform)

    return {
        "id": "ask_user",
        "output": json.dumps({
            "question": question.strip(),
            "response": response,
            "choices_offered": choices,
        }),
    }
