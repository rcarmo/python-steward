"""store_memory tool - persist facts for future tasks (aligned with Copilot CLI)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace

TOOL_DEFINITION: ToolDefinition = {
    "name": "store_memory",
    "description": "Store a fact about the codebase for future code generation or review tasks. Facts should be clear, concise statements about conventions, structure, logic, or usage.",
    "parameters": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "The topic this memory relates to (1-2 words). Examples: 'naming conventions', 'testing practices', 'authentication', 'error handling'.",
            },
            "fact": {
                "type": "string",
                "description": "A clear, short description of the fact (under 200 characters). Examples: 'Use JWT for authentication.', 'Follow PEP 257 docstring conventions.'",
            },
            "citations": {
                "type": "string",
                "description": "The source of this fact, such as a file and line number (e.g., 'path/file.go:123') or 'User input: ...'.",
            },
            "reason": {
                "type": "string",
                "description": "A clear explanation of why this fact is important and what future tasks it will help with (2-3 sentences).",
            },
            "category": {
                "type": "string",
                "enum": ["bootstrap_and_build", "user_preferences", "general", "file_specific"],
                "description": "The type of memory: 'bootstrap_and_build' (how to build/test), 'user_preferences' (coding style), 'general' (file-independent facts), or 'file_specific' (info about specific files).",
            },
        },
        "required": ["subject", "fact", "citations", "reason", "category"],
    },
}


def memory_file() -> Path:
    return Path.cwd() / ".steward-memory.json"


def load_memories(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        return data.get("memories", []) if isinstance(data, dict) else []
    except json.JSONDecodeError:
        return []


def tool_handler(args: Dict) -> ToolResult:
    subject = args.get("subject")
    fact = args.get("fact")
    citations = args.get("citations")
    reason = args.get("reason")
    category = args.get("category")

    # Validate required fields
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("'subject' must be a non-empty string")
    if not isinstance(fact, str) or not fact.strip():
        raise ValueError("'fact' must be a non-empty string")
    if len(fact) > 200:
        raise ValueError("'fact' must be under 200 characters")
    if not isinstance(citations, str) or not citations.strip():
        raise ValueError("'citations' must be a non-empty string")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("'reason' must be a non-empty string")
    valid_categories = {"bootstrap_and_build", "user_preferences", "general", "file_specific"}
    if category not in valid_categories:
        raise ValueError(f"'category' must be one of: {', '.join(valid_categories)}")

    mem_path = memory_file()
    ensure_inside_workspace(mem_path, must_exist=False)

    memories = load_memories(mem_path)

    # Check for duplicate facts
    for mem in memories:
        if mem.get("fact", "").lower() == fact.strip().lower():
            return {"id": "store_memory", "output": f"Memory already exists: {fact}"}

    new_memory = {
        "subject": subject.strip(),
        "fact": fact.strip(),
        "citations": citations.strip(),
        "reason": reason.strip(),
        "category": category,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    memories.append(new_memory)
    mem_path.write_text(json.dumps({"memories": memories}, indent=2), encoding="utf8")

    return {
        "id": "store_memory",
        "output": f"Stored memory [{category}]: {fact}\nSubject: {subject}\nCitations: {citations}",
    }
