from __future__ import annotations

import json
from pathlib import Path


def test_workspace_summary(tool_handlers, sandbox: Path):
    (sandbox / "package.json").write_text(json.dumps({"name": "pkg", "version": "1.0.0"}), encoding="utf8")
    (sandbox / "src").mkdir()
    (sandbox / "file.txt").write_text("x", encoding="utf8")
    summary = tool_handlers["workspace_summary"]({})
    assert "package: pkg@1.0.0" in summary["output"]
    assert "dirs: src" in summary["output"]
    assert "file.txt" in summary["output"]
