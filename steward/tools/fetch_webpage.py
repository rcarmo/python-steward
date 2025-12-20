"""fetch_webpage tool."""
from __future__ import annotations

import base64
from typing import Dict, List

import requests
from urllib.parse import unquote_to_bytes

from ..types import ToolDefinition, ToolResult
from .shared import env_cap, infer_content_type, strip_html, truncate_output

TOOL_DEFINITION: ToolDefinition = {
    "name": "fetch_webpage",
    "description": "Fetch main content from one or more web pages (stripped and truncated)",
    "parameters": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "query": {"type": "string"},
            "maxBytes": {"type": "number"},
            "textOnly": {"type": "boolean"},
        },
        "required": ["urls"],
    },
}


def _decode_data_url(url: str) -> tuple[str, str]:
    header, data_part = url.split(",", 1)
    content_type = infer_content_type(url) or ""
    if ";base64" in header:
        data = base64.b64decode(data_part)
    else:
        data = unquote_to_bytes(data_part)
    return content_type, data.decode("utf8", errors="ignore")


def fetch_one(url: str, max_bytes: int, text_only: bool) -> str:
    if url.startswith("data:"):
        content_type, text = _decode_data_url(url)
    else:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as exc:  # requests-specific or network errors
            return f"{url}: [error] {exc}"
        content_type = response.headers.get("content-type", infer_content_type(url) or "")
        text = response.text

    body = strip_html(text) if text_only else text
    limited = truncate_output(body, max_bytes)
    return f"{url}:\ncontent-type: {content_type}\n{limited}"


def tool_handler(args: Dict) -> ToolResult:
    urls_arg = args.get("urls")
    query = args.get("query") if isinstance(args.get("query"), str) else None
    max_bytes = args.get("maxBytes") if isinstance(args.get("maxBytes"), int) else env_cap("STEWARD_WEB_MAX_BYTES", 24000)
    text_only = args.get("textOnly") is not False

    if not isinstance(urls_arg, list) or not all(isinstance(u, str) for u in urls_arg):
        raise ValueError("'urls' must be an array of strings")

    urls: List[str] = urls_arg[:]
    outputs = [fetch_one(url, max_bytes, text_only) for url in urls]
    if query:
        outputs.append(f"query: {query}")
    return {"id": "fetch_webpage", "output": "\n\n".join(outputs)}
