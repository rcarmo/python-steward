"""fetch_data tool (download content with data: support)."""
from __future__ import annotations

import base64
from typing import Dict

import requests
from urllib.parse import unquote_to_bytes

from ..types import ToolDefinition, ToolResult
from .shared import env_cap, infer_content_type, strip_html, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "fetch_data",
    "description": "Download content from a URL (HTTP or data:), returning truncated body and type",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "maxBytes": {"type": "number"},
            "textOnly": {"type": "boolean"},
        },
        "required": ["url"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    url = args.get("url") if isinstance(args.get("url"), str) else None
    if url is None:
        raise ValueError("'url' must be a string")
    max_bytes = args.get("maxBytes") if isinstance(args.get("maxBytes"), int) else env_cap("STEWARD_WEB_MAX_BYTES", 24000)
    text_only = args.get("textOnly") is True

    content_type = infer_content_type(url) or ""
    data: bytes
    if url.startswith("data:"):
        parts = url.split(",", 1)
        data_part = parts[1] if len(parts) > 1 else ""
        if ";base64" in url.split(",", 1)[0]:
            data = base64.b64decode(data_part)
        else:
            data = unquote_to_bytes(data_part)
    else:
        response = requests.get(url, timeout=10)
        content_type = response.headers.get("content-type", content_type)
        data = response.content

    limited = data[:max_bytes]
    if text_only or (content_type and (content_type.startswith("text/") or "json" in content_type)):
        text = limited.decode("utf8", errors="ignore")
        output = strip_html(text) if text_only else text
    else:
        output = limited.decode("utf8", errors="ignore") if limited else ""
    final_output = truncate_output(output, max_bytes)
    return {
        "id": "fetch_data",
        "output": f"content-type: {content_type}\nbytes: {len(data)}\n{final_output}",
    }
