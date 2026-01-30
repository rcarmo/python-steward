"""list_memories tool - retrieve stored memory facts for the workspace."""

from __future__ import annotations

from typing import Optional

from ..types import ToolResult
from .shared import ensure_inside_workspace, env_cap
from .store_memory import load_memories, memory_file


def tool_list_memories(
    category: Optional[str] = None,
    subject: Optional[str] = None,
    limit: Optional[int] = None,
) -> ToolResult:
    """List stored memories from the workspace.

    Args:
        category: Optional category filter (bootstrap_and_build, user_preferences, general, file_specific)
        subject: Optional subject filter (case-insensitive exact match)
        limit: Max number of memories to return
    """
    mem_path = memory_file()
    ensure_inside_workspace(mem_path, must_exist=False)

    memories = load_memories(mem_path)
    if not memories:
        return {"id": "list_memories", "output": "No memories stored."}

    if category:
        valid_categories = {"bootstrap_and_build", "user_preferences", "general", "file_specific"}
        if category not in valid_categories:
            raise ValueError(f"'category' must be one of: {', '.join(valid_categories)}")
        memories = [mem for mem in memories if mem.get("category") == category]

    if subject:
        subject_norm = subject.strip().lower()
        memories = [mem for mem in memories if mem.get("subject", "").strip().lower() == subject_norm]

    if not memories:
        return {"id": "list_memories", "output": "No memories match the filters."}

    max_results = env_cap("STEWARD_MEMORY_MAX_RESULTS", 200)
    if limit is not None:
        if limit <= 0:
            raise ValueError("'limit' must be a positive integer")
        max_results = min(max_results, limit)

    memories = memories[:max_results]
    lines = []
    for idx, memory in enumerate(memories, start=1):
        lines.append(f"{idx}. Subject: {memory.get('subject', '').strip()}")
        lines.append(f"   Fact: {memory.get('fact', '').strip()}")
        lines.append(f"   Reason: {memory.get('reason', '').strip()}")
        lines.append(f"   Citations: {memory.get('citations', '').strip()}")
        lines.append(f"   Category: {memory.get('category', '').strip()}")
        if idx < len(memories):
            lines.append("")

    return {"id": "list_memories", "output": "\n".join(lines)}
