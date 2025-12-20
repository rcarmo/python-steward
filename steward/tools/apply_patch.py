"""apply_patch tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from unidiff import PatchSet

from ..types import ToolDefinition, ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path

TOOL_DEFINITION: ToolDefinition = {
    "name": "apply_patch",
    "description": "Apply a unified diff patch to a file",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "patch": {"type": "string"},
            "patches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "patch": {"type": "string"},
                    },
                    "required": ["path", "patch"],
                },
            },
            "dryRun": {"type": "boolean"},
        },
        "required": ["path", "patch"],
    },
}


def tool_handler(args: Dict) -> ToolResult:
    dry_run = args.get("dryRun") is True
    if isinstance(args.get("patches"), list):
        batch: List[Dict] = [item for item in args.get("patches", []) if isinstance(item, dict)]
        if not batch:
            raise ValueError("'patches' must be an array of {path, patch}")
        results: List[Tuple[Path, str]] = []
        for entry in batch:
            raw_path = entry.get("path")
            patch_text = entry.get("patch")
            if not isinstance(raw_path, str) or not isinstance(patch_text, str):
                raise ValueError("'patches' entries require path and patch strings")
            abs_path = normalize_path(raw_path)
            ensure_inside_workspace(abs_path)
            next_text = _apply_patch_to_file(abs_path, patch_text)
            if next_text is None:
                return {"id": "edit", "output": f"Patch could not be applied to {rel_path(abs_path)}", "error": True}
            results.append((abs_path, next_text))
        if dry_run:
            return {"id": "edit", "output": f"Dry-run OK for {len(results)} file(s)"}
        for abs_path, text in results:
            abs_path.write_text(text, encoding="utf8")
        return {"id": "edit", "output": f"Patched {len(results)} file(s)"}

    raw_path = args.get("path")
    patch_text = args.get("patch")
    if not isinstance(raw_path, str) or not isinstance(patch_text, str):
        raise ValueError("'path' and 'patch' must be strings")
    abs_path = normalize_path(raw_path)
    ensure_inside_workspace(abs_path)
    next_text = _apply_patch_to_file(abs_path, patch_text)
    if next_text is None:
        return {"id": "edit", "output": "Patch could not be applied", "error": True}
    if dry_run:
        return {"id": "edit", "output": f"Dry-run OK for {rel_path(abs_path)}"}
    abs_path.write_text(next_text, encoding="utf8")
    return {"id": "edit", "output": f"Patched {rel_path(abs_path)}"}


def _apply_patch_to_file(abs_path: Path, patch_text: str) -> str | None:
    if not abs_path.exists():
        return None
    original = abs_path.read_text(encoding="utf8")
    patch = PatchSet(patch_text)
    if len(patch) == 0:
        return None
    patched = original
    for file_patch in patch:
        patched = _apply_file_patch(patched, file_patch)
        if patched is None:
            return None
    return patched


def _apply_file_patch(content: str, file_patch) -> str | None:
    lines = content.splitlines(keepends=True)
    new_lines: List[str] = []
    index = 0
    for hunk in file_patch:
        start = hunk.source_start - 1
        if start > len(lines):
            return None
        while index < start:
            new_lines.append(lines[index])
            index += 1
        for line in hunk:
            if line.is_added:  # type: ignore[attr-defined]
                new_lines.append(line.value)
            elif line.is_removed:  # type: ignore[attr-defined]
                if index >= len(lines) or lines[index] != line.value:
                    return None
                index += 1
            else:
                if index >= len(lines) or lines[index] != line.value:
                    return None
                new_lines.append(lines[index])
                index += 1
    new_lines.extend(lines[index:])
    return "".join(new_lines)
