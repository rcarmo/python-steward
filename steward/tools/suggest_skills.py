"""suggest_skills tool - find skills matching a query."""
from __future__ import annotations

from ..skills import get_registry
from ..types import ToolResult


def tool_suggest_skills(query: str, limit: int = 5) -> ToolResult:
    """Find skills that match a query or task description.

    Args:
        query: The task or query to match against skills
        limit: Maximum number of skills to return (default: 5)
    """
    if not query or not query.strip():
        return {"id": "suggest_skills", "output": "Query is required."}

    registry = get_registry()

    # Auto-discover if not already done
    if not registry.is_discovered:
        count = registry.discover()
        if count == 0:
            return {"id": "suggest_skills", "output": "No skills discovered in workspace. Create SKILL.md files to define skills."}

    matches = registry.match(query, limit=limit)
    output = registry.format_suggestions(matches)

    return {"id": "suggest_skills", "output": output}
