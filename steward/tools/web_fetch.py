"""web_fetch tool - fetch URL and return as markdown or raw HTML."""
from __future__ import annotations

import base64
import re
from typing import Dict
from urllib.parse import unquote_to_bytes

import requests

from ..types import ToolDefinition, ToolResult
from .shared import env_cap, infer_content_type

TOOL_DEFINITION: ToolDefinition = {
    "name": "web_fetch",
    "description": "Fetch a URL and return the page as either markdown or raw HTML",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
            "raw": {
                "type": "boolean",
                "description": "If true, returns raw HTML. If false, converts to simplified markdown (default: false)",
            },
            "max_length": {
                "type": "number",
                "description": "Maximum number of characters to return (default: 5000, maximum: 20000)",
            },
            "start_index": {
                "type": "number",
                "description": "Start index for pagination. Use this to continue reading if content was truncated (default: 0)",
            },
        },
        "required": ["url"],
    },
}

DEFAULT_MAX_LENGTH = 5000
MAX_ALLOWED_LENGTH = 20000


def _html_to_markdown(html: str) -> str:
    """Convert HTML to simplified markdown."""
    text = html
    # Remove script and style tags with content
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert headers
    for i in range(1, 7):
        text = re.sub(rf"<h{i}[^>]*>(.*?)</h{i}>", rf"{'#' * i} \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert paragraphs
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Convert links
    text = re.sub(r"<a[^>]*href=[\"']([^\"']*)[\"'][^>]*>(.*?)</a>", r"[\2](\1)", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert bold/strong
    text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert italic/em
    text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert code
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert pre blocks
    text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"```\n\1\n```", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert lists
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    # Normalize whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _decode_data_url(url: str) -> tuple[str, str]:
    """Decode a data: URL and return (content_type, content)."""
    parts = url.split(",", 1)
    header = parts[0]
    data_part = parts[1] if len(parts) > 1 else ""
    content_type = infer_content_type(url) or "text/plain"
    if ";base64" in header:
        data = base64.b64decode(data_part)
    else:
        data = unquote_to_bytes(data_part)
    return content_type, data.decode("utf8", errors="ignore")


def tool_handler(args: Dict) -> ToolResult:
    url = args.get("url")
    if not isinstance(url, str):
        raise ValueError("'url' must be a string")

    raw = args.get("raw", False) is True
    max_length = args.get("max_length")
    if not isinstance(max_length, int) or max_length <= 0:
        max_length = env_cap("STEWARD_WEB_MAX_LENGTH", DEFAULT_MAX_LENGTH)
    max_length = min(max_length, MAX_ALLOWED_LENGTH)
    start_index = args.get("start_index")
    if not isinstance(start_index, int) or start_index < 0:
        start_index = 0

    content_type: str
    content: str

    if url.startswith("data:"):
        content_type, content = _decode_data_url(url)
    else:
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "Steward/1.0"})
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"id": "web_fetch", "output": f"[error] {exc}"}
        content_type = response.headers.get("content-type", "text/html")
        content = response.text

    # Convert to markdown unless raw requested
    if not raw and "html" in content_type.lower():
        content = _html_to_markdown(content)

    # Apply pagination
    total_length = len(content)
    paginated = content[start_index:start_index + max_length]
    truncated = start_index + len(paginated) < total_length

    output_lines = [f"url: {url}", f"content-type: {content_type}"]
    if truncated:
        output_lines.append(f"[truncated at {start_index + len(paginated)}/{total_length} chars, use start_index={start_index + len(paginated)} to continue]")
    output_lines.append("")
    output_lines.append(paginated)

    return {"id": "web_fetch", "output": "\n".join(output_lines)}
