"""suggest_skills tool - find skills matching a query."""
from __future__ import annotations

from typing import Dict

from ..skills import get_registry
from ..types import ToolDefinition, ToolResult

TOOL_DEFINITION: ToolDefinition = {
    "name": "suggest_skills",
    "description": "Find skills that match a query or task description. Returns ranked list of relevant skills based on triggers, description, and name matching.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The task or query to match against skills (e.g., 'create generative art', 'build MCP server').",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of skills to return (default: 5).",
            },
        },
        "required": ["query"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    query = args.get("query", "")
    if not query or not isinstance(query, str):
        return {"id": "suggest_skills", "output": "Query is required."}

    limit = args.get("limit", 5)
    if not isinstance(limit, int) or limit < 1:
        limit = 5

    registry = get_registry()

    # Auto-discover if not already done
    if not registry.is_discovered:
        count = registry.discover()
        if count == 0:
            return {"id": "suggest_skills", "output": "No skills discovered in workspace. Create SKILL.md files to define skills."}

    matches = registry.match(query, limit=limit)
    output = registry.format_suggestions(matches)

    return {"id": "suggest_skills", "output": output}
