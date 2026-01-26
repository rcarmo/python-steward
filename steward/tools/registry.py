"""Discover tool definitions and handlers from steward.tools.* modules.

Supports umcp-style tool discovery where tool_handler functions use
typed parameters and docstrings instead of TOOL_DEFINITION dicts.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Callable, Dict, List, Tuple, Union, get_args, get_origin, get_type_hints

from ..types import ToolDefinition, ToolHandler


def _type_to_json_schema(param_type: Any) -> Dict[str, Any]:
    """Convert Python type annotation to JSON schema property."""
    if param_type is None or param_type is type(None):
        return {"type": "string"}
    elif param_type is str:
        return {"type": "string"}
    elif param_type is int:
        return {"type": "integer"}
    elif param_type is float:
        return {"type": "number"}
    elif param_type is bool:
        return {"type": "boolean"}
    elif param_type is list:
        return {"type": "array"}
    elif param_type is dict:
        return {"type": "object"}

    # Handle Union types (e.g., Optional[str])
    origin = get_origin(param_type)
    if origin is Union:
        args = get_args(param_type)
        # Handle Optional[T] which is Union[T, None]
        if len(args) == 2 and type(None) in args:
            non_none_type = args[0] if args[1] is type(None) else args[1]
            return _type_to_json_schema(non_none_type)

    # Handle generic types like List[str], Dict[str, Any]
    if origin is list:
        args = get_args(param_type)
        schema: Dict[str, Any] = {"type": "array"}
        if args:
            schema["items"] = _type_to_json_schema(args[0])
        return schema
    elif origin is dict:
        return {"type": "object"}

    # Default to string for unknown types
    return {"type": "string"}


def _extract_parameters_from_signature(handler: Callable) -> Dict[str, Any]:
    """Extract parameter schema from function signature and type hints."""
    sig = inspect.signature(handler)

    try:
        type_hints = get_type_hints(handler)
    except (NameError, AttributeError, TypeError):
        type_hints = {}

    # Skip 'args' parameter (legacy dict-style handlers)
    params = [(name, param) for name, param in sig.parameters.items()
              if name not in ("self", "args", "kwargs")]

    if not params:
        return {"type": "object", "properties": {}}

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for name, param in params:
        param_type = type_hints.get(name, param.annotation)
        if param_type == inspect.Parameter.empty:
            param_type = str  # Default to string
        properties[name] = _type_to_json_schema(param_type)
        if param.default == inspect.Parameter.empty:
            required.append(name)

    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _build_definition_from_handler(name: str, handler: Callable) -> ToolDefinition:
    """Build a ToolDefinition from a handler function's signature and docstring."""
    docstring = inspect.getdoc(handler) or f"Execute {name} tool"
    parameters = _extract_parameters_from_signature(handler)

    return {
        "name": name,
        "description": docstring,
        "parameters": parameters,
    }


def _create_wrapper(handler: Callable) -> ToolHandler:
    """Create a wrapper that converts dict args to typed parameters."""
    sig = inspect.signature(handler)
    params = [(name, param) for name, param in sig.parameters.items()
              if name not in ("self", "kwargs")]

    # Check if it's already a dict-style handler
    if len(params) == 1 and params[0][0] == "args":
        return handler

    def wrapper(args: Dict) -> Any:
        kwargs = {}
        for name, param in params:
            if name in args:
                kwargs[name] = args[name]
            elif param.default != inspect.Parameter.empty:
                kwargs[name] = param.default
            # Skip missing optional params (they'll use function defaults)
        return handler(**kwargs)

    return wrapper


def discover_tools() -> Tuple[List[ToolDefinition], Dict[str, ToolHandler]]:
    """Discover tools from steward.tools.* modules.

    Supports two formats:
    1. Legacy: TOOL_DEFINITION dict + tool_handler(args: Dict) function
    2. umcp-style: tool_handler with typed params and docstring (auto-generates definition)
    """
    definitions: List[ToolDefinition] = []
    handlers: Dict[str, ToolHandler] = {}
    package_name = __name__.rsplit(".", 1)[0]
    package = importlib.import_module(package_name)

    for module_info in pkgutil.iter_modules(package.__path__):
        name = module_info.name
        if name.startswith("_") or name in {"registry", "shared"}:
            continue

        module = importlib.import_module(f"{package_name}.{name}")
        handler = getattr(module, "tool_handler", None)

        if not handler:
            continue

        # Check for explicit TOOL_DEFINITION first (legacy format)
        definition = getattr(module, "TOOL_DEFINITION", None)

        if definition:
            # Use explicit definition
            definitions.append(definition)
            handlers[definition["name"]] = handler
        else:
            # Auto-generate from handler signature and docstring
            # Use module name as tool name (underscores preserved for compatibility)
            tool_name = name
            auto_def = _build_definition_from_handler(tool_name, handler)
            definitions.append(auto_def)
            handlers[tool_name] = _create_wrapper(handler)

    return definitions, handlers
