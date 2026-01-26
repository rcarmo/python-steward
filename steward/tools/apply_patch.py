"""apply_patch tool."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from unidiff import PatchSet

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def tool_handler(
    path: Optional[str] = None,
    patch: Optional[str] = None,
    patches: Optional[List[Dict[str, str]]] = None,
    dryRun: bool = False,
) -> ToolResult:
    """Apply a unified diff patch to a file.

    Args:
        path: Path to the file to patch (required for single file mode)
        patch: The unified diff patch content to apply (required for single file mode)
        patches: Array of {path, patch} objects for batch mode
        dryRun: If true, validate patch without applying
    """
    if patches is not None:
        batch: List[Dict[str, str]] = [item for item in patches if isinstance(item, dict)]
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
        if dryRun:
            return {"id": "edit", "output": f"Dry-run OK for {len(results)} file(s)"}
        for abs_path, text in results:
            abs_path.write_text(text, encoding="utf8")
        return {"id": "edit", "output": f"Patched {len(results)} file(s)"}

    # Single file mode - path and patch are required
    if not path or not patch:
        raise ValueError("'path' and 'patch' are required for single file mode")

    abs_path = normalize_path(path)
    ensure_inside_workspace(abs_path)
    next_text = _apply_patch_to_file(abs_path, patch)
    if next_text is None:
        return {"id": "edit", "output": "Patch could not be applied", "error": True}
    if dryRun:
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
