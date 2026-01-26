"""store_memory tool - persist facts for future tasks (aligned with Copilot CLI)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..types import ToolResult
from .shared import ensure_inside_workspace


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


def tool_store_memory(subject: str, fact: str, citations: str, reason: str, category: str) -> ToolResult:
    """Store a fact about the codebase for future code generation or review tasks.

    Args:
        subject: The topic this memory relates to (1-2 words)
        fact: A clear, short description of the fact (under 200 characters)
        citations: The source of this fact (e.g., 'path/file.go:123')
        reason: Explanation of why this fact is important (2-3 sentences)
        category: Type: bootstrap_and_build, user_preferences, general, or file_specific
    """
    # Validate required fields
    if not subject or not subject.strip():
        raise ValueError("'subject' must be a non-empty string")
    if not fact or not fact.strip():
        raise ValueError("'fact' must be a non-empty string")
    if len(fact) > 200:
        raise ValueError("'fact' must be under 200 characters")
    if not citations or not citations.strip():
        raise ValueError("'citations' must be a non-empty string")
    if not reason or not reason.strip():
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
