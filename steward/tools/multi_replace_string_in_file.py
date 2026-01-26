"""multi_replace_string_in_file tool."""
from __future__ import annotations

from typing import Dict, List

from ..types import ToolResult
from .shared import ensure_inside_workspace, normalize_path, rel_path


def tool_handler(replacements: List[Dict[str, str]]) -> ToolResult:
    """Apply multiple string replacements across files.

    Args:
        replacements: Array of replacement objects with path, oldString, newString
    """
    if not replacements:
        raise ValueError("'replacements' cannot be empty")

    results: List[str] = []
    errors: List[str] = []

    for idx, replacement in enumerate(replacements):
        if not isinstance(replacement, dict):
            errors.append(f"Replacement {idx + 1}: Not a valid object")
            continue

        raw_path = replacement.get("path")
        old_string = replacement.get("oldString")
        new_string = replacement.get("newString")

        if not isinstance(raw_path, str):
            errors.append(f"Replacement {idx + 1}: 'path' must be a string")
            continue
        if not isinstance(old_string, str):
            errors.append(f"Replacement {idx + 1}: 'oldString' must be a string")
            continue
        if not isinstance(new_string, str):
            errors.append(f"Replacement {idx + 1}: 'newString' must be a string")
            continue

        try:
            abs_path = normalize_path(raw_path)
            ensure_inside_workspace(abs_path)

            if not abs_path.exists():
                errors.append(f"Replacement {idx + 1}: File does not exist: {rel_path(abs_path)}")
                continue

            content = abs_path.read_text(encoding="utf8")

            if old_string not in content:
                errors.append(f"Replacement {idx + 1}: String not found in {rel_path(abs_path)}")
                continue

            occurrences = content.count(old_string)
            if occurrences > 1:
                errors.append(f"Replacement {idx + 1}: String appears {occurrences} times in {rel_path(abs_path)}; must be unique")
                continue

            new_content = content.replace(old_string, new_string, 1)
            abs_path.write_text(new_content, encoding="utf8")

            results.append(f"✓ {rel_path(abs_path)}")
        except Exception as e:
            errors.append(f"Replacement {idx + 1}: {str(e)}")

    summary_parts: List[str] = []
    if results:
        summary_parts.append(f"Successfully replaced in {len(results)} file(s):\n" + "\n".join(results))
    if errors:
        summary_parts.append(f"\nFailed {len(errors)} replacement(s):\n" + "\n".join(errors))

    output = "\n".join(summary_parts)
    has_error = bool(errors)

    return {"id": "multi_replace_string_in_file", "output": output, "error": has_error}
