"""Discover tool and prompt definitions from steward.tools.* modules.

Supports umcp-style discovery where:
- Functions named tool_<name> are discovered as tools
- Functions named prompt_<name> are discovered as prompts
- Type hints on parameters generate JSON schema
- Docstrings provide descriptions

CACHING NOTE: Tool definitions are sorted alphabetically by name to ensure
consistent ordering across requests. This maximizes prompt cache hit rates
since OpenAI caches prompts with identical prefixes (first 1024+ tokens).
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from os import getenv
from typing import Any, Callable, Dict, List, Tuple, Union, get_args, get_origin, get_type_hints

from ..types import ToolDefinition, ToolHandler

# Tools that require STEWARD_ALLOW_EXECUTE=1 to be visible
EXECUTE_TOOLS = {"bash", "read_bash", "write_bash", "stop_bash", "list_bash"}

# Tools that require MCP servers to be configured
MCP_TOOLS = {"mcp_list_servers", "mcp_list_tools", "mcp_call"}


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
    params = [(name, param) for name, param in sig.parameters.items() if name not in ("self", "args", "kwargs")]

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
    params = [(name, param) for name, param in sig.parameters.items() if name not in ("self", "kwargs")]

    # Check if it's already a dict-style handler
    if len(params) == 1 and params[0][0] == "args":
        return handler

    def _build_kwargs(args: Dict) -> Dict:
        if args is None:
            args = {}
        kwargs = {}
        missing = []
        for name, param in params:
            if name in args:
                kwargs[name] = args[name]
            elif param.default != inspect.Parameter.empty:
                kwargs[name] = param.default
            else:
                missing.append(name)
        if missing:
            raise ValueError(
                f"'{', '.join(missing)}' {'is' if len(missing) == 1 else 'are'} required and must be provided"
            )
        return kwargs

    # Create async wrapper if handler is async
    if inspect.iscoroutinefunction(handler):

        async def async_wrapper(args: Dict) -> Any:
            return await handler(**_build_kwargs(args))

        return async_wrapper

    def wrapper(args: Dict) -> Any:
        return handler(**_build_kwargs(args))

    return wrapper


def _discover_from_module(module: Any) -> Tuple[List[Tuple[str, Callable]], List[Tuple[str, Callable]]]:
    """Discover tool_ and prompt_ prefixed functions from a module.

    Returns (tools, prompts) where each is a list of (name, handler) tuples.
    """
    tools: List[Tuple[str, Callable]] = []
    prompts: List[Tuple[str, Callable]] = []

    for attr_name in dir(module):
        if attr_name.startswith("tool_"):
            handler = getattr(module, attr_name)
            if callable(handler):
                # Extract tool name from function name (tool_view -> view)
                tool_name = attr_name[5:]  # Remove "tool_" prefix
                tools.append((tool_name, handler))
        elif attr_name.startswith("prompt_"):
            handler = getattr(module, attr_name)
            if callable(handler):
                prompt_name = attr_name[7:]  # Remove "prompt_" prefix
                prompts.append((prompt_name, handler))

    return tools, prompts


def _has_mcp_servers() -> bool:
    """Check if any MCP servers are configured."""
    from ..mcp_client import load_config

    return bool(load_config())


def discover_tools() -> Tuple[List[ToolDefinition], Dict[str, ToolHandler]]:
    """Discover tools from steward.tools.* modules.

    Supports two formats:
    1. Legacy: TOOL_DEFINITION dict + tool_handler(args: Dict) function
    2. umcp-style: tool_<name> functions with typed params and docstring

    Tools in EXECUTE_TOOLS are hidden when STEWARD_ALLOW_EXECUTE != "1".
    Tools in MCP_TOOLS are hidden when no MCP servers are configured.

    Returns definitions sorted by name for prompt caching stability.
    """
    definitions: List[ToolDefinition] = []
    handlers: Dict[str, ToolHandler] = {}
    package_name = __name__.rsplit(".", 1)[0]
    package = importlib.import_module(package_name)
    execute_enabled = getenv("STEWARD_ALLOW_EXECUTE") == "1"
    mcp_enabled = _has_mcp_servers()

    for module_info in pkgutil.iter_modules(package.__path__):
        name = module_info.name
        if name.startswith("_") or name in {"registry", "shared"}:
            continue

        module = importlib.import_module(f"{package_name}.{name}")

        # First try umcp-style discovery (tool_ prefix)
        tools, _ = _discover_from_module(module)

        if tools:
            # Use umcp-style discovered tools
            for tool_name, handler in tools:
                # Skip execute tools if execution disabled
                if tool_name in EXECUTE_TOOLS and not execute_enabled:
                    continue
                # Skip MCP tools if no servers configured
                if tool_name in MCP_TOOLS and not mcp_enabled:
                    continue
                auto_def = _build_definition_from_handler(tool_name, handler)
                definitions.append(auto_def)
                handlers[tool_name] = _create_wrapper(handler)
        else:
            # Fall back to legacy tool_handler discovery
            handler = getattr(module, "tool_handler", None)
            if not handler:
                continue

            # Check for explicit TOOL_DEFINITION (legacy format)
            definition = getattr(module, "TOOL_DEFINITION", None)

            if definition:
                definitions.append(definition)
                handlers[definition["name"]] = handler
            else:
                # Auto-generate from handler signature
                tool_name = name
                auto_def = _build_definition_from_handler(tool_name, handler)
                definitions.append(auto_def)
                handlers[tool_name] = _create_wrapper(handler)

    # Sort definitions by name for prompt caching stability (Codex pattern)
    definitions.sort(key=lambda d: d["name"])
    return definitions, handlers


def discover_prompts() -> Dict[str, Callable]:
    """Discover prompts from steward.tools.* modules.

    Looks for prompt_<name> functions and returns a dict of name -> handler.
    """
    prompts: Dict[str, Callable] = {}
    package_name = __name__.rsplit(".", 1)[0]
    package = importlib.import_module(package_name)

    for module_info in pkgutil.iter_modules(package.__path__):
        name = module_info.name
        if name.startswith("_") or name in {"registry", "shared"}:
            continue

        module = importlib.import_module(f"{package_name}.{name}")
        _, module_prompts = _discover_from_module(module)

        for prompt_name, handler in module_prompts:
            prompts[prompt_name] = handler

    return prompts
