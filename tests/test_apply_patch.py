"""Tests for apply_patch tool."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def patch_file(sandbox: Path):
    """Create a file and return a patch for it."""

    def _create(filename: str, old: str, new: str):
        (sandbox / filename).write_text(old + "\n", encoding="utf8")
        return "\n".join([f"--- a/{filename}", f"+++ b/{filename}", "@@ -1 +1 @@", f"-{old}", f"+{new}", ""])

    return _create


def test_apply_patch(tool_handlers, sandbox: Path, patch_file):
    patch = patch_file("patch.txt", "old", "new")
    result = tool_handlers["apply_patch"]({"path": "patch.txt", "patch": patch})
    assert "Patched patch.txt" in result["output"]
    assert (sandbox / "patch.txt").read_text(encoding="utf8").strip() == "new"


@pytest.mark.parametrize(
    "dry_run,bad_patch,expected",
    [
        (True, False, "Dry-run OK"),
        (False, True, True),  # error flag
    ],
)
def test_apply_patch_modes(tool_handlers, sandbox: Path, patch_file, dry_run, bad_patch, expected):
    patch = patch_file("dry.txt", "hello", "hi")
    if bad_patch:
        patch = "\n".join(["--- a/dry.txt", "+++ b/dry.txt", "@@ -1 +1 @@", "-missing", "+oops", ""])

    args = {"path": "dry.txt", "patch": patch}
    if dry_run:
        args["dryRun"] = True

    result = tool_handlers["apply_patch"](args)
    if isinstance(expected, bool):
        assert result.get("error") is expected
    else:
        assert expected in result["output"]


def test_apply_patch_batch(tool_handlers, sandbox: Path):
    (sandbox / "a.txt").write_text("a\n", encoding="utf8")
    (sandbox / "b.txt").write_text("b\n", encoding="utf8")
    patches = [
        {"path": "a.txt", "patch": "\n".join(["--- a/a.txt", "+++ b/a.txt", "@@ -1 +1 @@", "-a", "+aa", ""])},
        {"path": "b.txt", "patch": "\n".join(["--- a/b.txt", "+++ b/b.txt", "@@ -1 +1 @@", "-b", "+bb", ""])},
    ]

    dry = tool_handlers["apply_patch"]({"patches": patches, "dryRun": True})
    assert "Dry-run OK for 2 file(s)" in dry["output"]

    applied = tool_handlers["apply_patch"]({"patches": patches})
    assert "Patched 2 file(s)" in applied["output"]
    assert (sandbox / "a.txt").read_text(encoding="utf8").strip() == "aa"
    assert (sandbox / "b.txt").read_text(encoding="utf8").strip() == "bb"
