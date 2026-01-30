"""Shared helpers for tool implementations."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from ..config import DEFAULT_TOOL_OUTPUT_LIMIT, env_int, get_sandbox_root

TodoStatus = str

# Crawler-like User-Agent for web_fetch (Bingbot-like)
CRAWLER_USER_AGENT = "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)"

# Standard browser User-Agent for DuckDuckGo searches (WebKit/Safari)
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
)


def truncate_tool_output(output: str, max_chars: int = DEFAULT_TOOL_OUTPUT_LIMIT) -> str:
    """
    Truncate tool output to fit within context limits (Codex-style).

    Prevents context window blowup from verbose tool outputs.
    Adds clear marker so model knows output was truncated.
    """
    if len(output) <= max_chars:
        return output
    # Try to truncate at a line boundary
    truncated = output[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.8:  # Only if we don't lose too much
        truncated = truncated[:last_newline]
    return truncated + "\n[...output truncated, use view_range or pagination for more]"


def print_status(message: str) -> None:
    """Print a transient status message to stderr."""
    # Using ANSI escape codes: save cursor, print, restore cursor
    sys.stderr.write(f"\r\033[K  ⋯ {message}")
    sys.stderr.flush()


def clear_status() -> None:
    """Clear the transient status line."""
    sys.stderr.write("\r\033[K")
    sys.stderr.flush()


def get_workspace_root() -> Path:
    """Get the effective workspace root (sandbox root if set, else cwd)."""
    sandbox = get_sandbox_root()
    return sandbox if sandbox else Path.cwd().resolve()


def normalize_path(path: str) -> Path:
    return (Path.cwd() / path).resolve()


def rel_path(abs_path: Path) -> str:
    try:
        return str(abs_path.relative_to(Path.cwd()))
    except ValueError:
        return abs_path.name


def ensure_inside_workspace(abs_path: Path, must_exist: bool = True) -> None:
    """Ensure path is inside workspace. Uses sandbox root if set, else cwd."""
    root = get_workspace_root()
    try:
        target = abs_path.resolve(strict=must_exist)
    except FileNotFoundError:
        if must_exist:
            raise
        target = abs_path.parent.resolve()
    if root not in target.parents and target != root:
        raise ValueError(f"Path outside workspace: {abs_path}")


def walk(root: Path, visit: Callable[[Path], None], stop: Callable[[], bool] | None = None) -> None:
    if stop and stop():
        return
    if root.is_dir():
        for entry in root.iterdir():
            if entry.name in {"node_modules", ".git"}:
                continue
            if stop and stop():
                break
            walk(entry, visit, stop)
    elif root.is_file():
        visit(root)


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def infer_content_type(url: str) -> str | None:
    match = re.match(r"^data:([^;,]+)[;,]", url, re.IGNORECASE)
    return match.group(1) if match else None


def is_hidden(rel: str) -> bool:
    return any(part.startswith(".") and part != "." for part in Path(rel).parts)


def is_binary_buffer(data: bytes) -> bool:
    return b"\x00" in data


def truncate_output(body: str, max_bytes: int) -> str:
    encoded = body.encode("utf8")
    if len(encoded) <= max_bytes:
        return body
    truncated = encoded[:max_bytes]
    return f"{truncated.decode('utf8', errors='ignore')}\n[truncated]"


def build_matcher(
    pattern: str, *, is_regex: bool, case_sensitive: bool, smart_case: bool, fixed_string: bool, word_match: bool
) -> Callable[[str], bool]:
    effective_case_sensitive = case_sensitive
    if not case_sensitive and smart_case and any(ch.isupper() for ch in pattern):
        effective_case_sensitive = True
    flags = 0 if effective_case_sensitive else re.IGNORECASE
    if not is_regex:
        escaped = re.escape(pattern) if fixed_string or word_match else pattern
        source = rf"\b{escaped}\b" if word_match else escaped
        regex = re.compile(source, flags)
        return lambda line: bool(regex.search(line))
    regex = re.compile(pattern, flags)
    return lambda line: bool(regex.search(line))


def run_captured(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def audit_execute(entry: dict) -> None:
    try:
        log_path = Path.cwd() / ".steward-exec-audit.log"
        record = {"ts": entry.get("ts"), **{k: v for k, v in entry.items() if k != "ts"}}
        with log_path.open("a", encoding="utf8") as handle:
            handle.write(json.dumps(record))
            handle.write("\n")
    except OSError:
        pass


def read_todo(file: Path) -> dict:
    if not file.exists():
        return {"nextId": 1, "items": []}
    try:
        return json.loads(file.read_text(encoding="utf8"))
    except json.JSONDecodeError:
        return {"nextId": 1, "items": []}


def write_todo(file: Path, data: dict) -> None:
    file.write_text(json.dumps(data, indent=2), encoding="utf8")


def env_cap(name: str, fallback: int) -> int:
    return env_int(name, fallback)
