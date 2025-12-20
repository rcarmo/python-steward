"""Discover tool definitions and handlers from steward.tools.* modules."""
from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, List, Tuple

from ..types import ToolDefinition, ToolHandler


def discover_tools() -> Tuple[List[ToolDefinition], Dict[str, ToolHandler]]:
    definitions: List[ToolDefinition] = []
    handlers: Dict[str, ToolHandler] = {}
    package_name = __name__.rsplit(".", 1)[0]
    package = importlib.import_module(package_name)
    for module_info in pkgutil.iter_modules(package.__path__):
        name = module_info.name
        if name.startswith("_") or name in {"registry"}:
            continue
        module = importlib.import_module(f"{package_name}.{name}")
        definition = getattr(module, "TOOL_DEFINITION", None)
        handler = getattr(module, "tool_handler", None)
        if definition and handler:
            definitions.append(definition)
            handlers[definition["name"]] = handler
    return definitions, handlers
