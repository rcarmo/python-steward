"""Shared helpers for tool implementations."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Iterable, List

from ..config import env_int

TodoStatus = str


def normalize_path(path: str) -> Path:
    return (Path.cwd() / path).resolve()


def rel_path(abs_path: Path) -> str:
    try:
        return str(abs_path.relative_to(Path.cwd()))
    except ValueError:
        return abs_path.name


def ensure_inside_workspace(abs_path: Path, must_exist: bool = True) -> None:
    root = Path.cwd().resolve()
    try:
        target = abs_path.resolve(strict=must_exist)
    except FileNotFoundError:
        if must_exist:
            raise
        target = abs_path.parent.resolve()
    if root not in target.parents and target != root:
        raise ValueError("Path outside workspace")


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


def build_matcher(pattern: str, *, is_regex: bool, case_sensitive: bool, smart_case: bool, fixed_string: bool, word_match: bool) -> Callable[[str], bool]:
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
