"""General utilities shared across steward modules."""
from __future__ import annotations

import json
from typing import Any


def safe_json(value: Any) -> str:
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return "<unserializable>"


def truncate_output(body: str, max_bytes: int) -> str:
    encoded = body.encode("utf8")
    if len(encoded) <= max_bytes:
        return body
    truncated = encoded[:max_bytes]
    return f"{truncated.decode('utf8', errors='ignore')}\n[truncated]"
