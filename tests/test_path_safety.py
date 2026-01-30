"""Tests for path safety."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_symlink_escape(tool_handlers, sandbox: Path, tmp_path_factory):
    outside_dir = tmp_path_factory.mktemp("steward-outside")
    outside = outside_dir / "outside.txt"
    outside.write_text("oops", encoding="utf8")
    link_path = sandbox / "link.txt"
    os.symlink(outside, link_path)
    with pytest.raises(Exception):
        tool_handlers["read_file"]({"path": "link.txt"})
