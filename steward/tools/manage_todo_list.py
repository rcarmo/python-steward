"""manage_todo_list tool (Copilot-style plan)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from filelock import FileLock

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace

TOOL_DEFINITION: ToolDefinition = {
    "name": "manage_todo_list",
    "description": "Update the conversation plan todo list (Copilot-style)",
    "parameters": {
        "type": "object",
        "properties": {
            "todoList": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "number"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["not-started", "in-progress", "completed", "blocked", "done"],
                        },
                    },
                    "required": ["id", "title", "status"],
                },
            }
        },
        "required": ["todoList"],
    },
}

def plan_file() -> Path:
    return Path.cwd() / ".steward-plan.json"


def lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def validate_items(items: List[dict]) -> List[dict]:
    validated: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each todo must be an object")
        if not isinstance(item.get("id"), int):
            raise ValueError("Todo id must be an integer")
        if not isinstance(item.get("title"), str):
            raise ValueError("Todo title must be a string")
        status = normalize_status(item.get("status"))
        if not status:
            raise ValueError("Invalid status")
        description = item.get("description") if isinstance(item.get("description"), str) else ""
        validated.append(
            {
                "id": item["id"],
                "title": item["title"].strip(),
                "description": description.strip(),
                "status": status,
            }
        )
    return validated


def format_plan(items: List[dict]) -> str:
    lines = []
    for itm in items:
        desc = f" - {itm['description']}" if itm.get("description") else ""
        lines.append(f"{itm['id']}. [{itm['status']}] {itm['title']}{desc}")
    return "\n".join(lines) or "No todos"


def load_plan(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        items = data.get("items", []) if isinstance(data, dict) else []
        return validate_items(items)
    except json.JSONDecodeError:
        return []


def merge_items(existing: List[dict], incoming: List[dict]) -> List[dict]:
    merged = {item["id"]: item for item in existing}
    for item in incoming:
        merged[item["id"]] = item
    return list(merged.values())


def tool_handler(args: Dict) -> ToolResult:
    todo_list = args.get("todoList")
    if not isinstance(todo_list, list):
        raise ValueError("'todoList' must be an array")

    incoming = validate_items(todo_list)

    plan_path = plan_file()
    ensure_inside_workspace(plan_path, must_exist=False)
    lock = FileLock(lock_path(plan_path))
    with lock:
        existing = load_plan(plan_path)
        merged = merge_items(existing, incoming)
        plan_path.write_text(json.dumps({"items": merged}, indent=2), encoding="utf8")

    return {
        "id": "manage_todo_list",
        "output": format_plan(merged),
        "planPath": str(plan_path),
    }


def normalize_status(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    lowered = raw.strip().lower()
    aliases = {"done": "completed", "blocked": "in-progress"}
    if lowered in {"not-started", "in-progress", "completed"}:
        return lowered
    return aliases.get(lowered, "")
