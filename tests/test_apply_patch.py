from __future__ import annotations

from pathlib import Path


def test_apply_patch(tool_handlers, sandbox: Path):
    file_path = sandbox / "patch.txt"
    file_path.write_text("old\n", encoding="utf8")
    patch = "\n".join(["--- a/patch.txt", "+++ b/patch.txt", "@@ -1 +1 @@", "-old", "+new", ""])
    result = tool_handlers["apply_patch"]({"path": "patch.txt", "patch": patch})
    assert "Patched patch.txt" in result["output"]
    assert file_path.read_text(encoding="utf8").strip() == "new"


def test_dry_run_and_failure(tool_handlers, sandbox: Path):
    file_path = sandbox / "dry.txt"
    file_path.write_text("hello\n", encoding="utf8")
    patch = "\n".join(["--- a/dry.txt", "+++ b/dry.txt", "@@ -1 +1 @@", "-hello", "+hi", ""])
    dry = tool_handlers["apply_patch"]({"path": "dry.txt", "patch": patch, "dryRun": True})
    assert "Dry-run OK" in dry["output"]
    bad_patch = "\n".join(["--- a/dry.txt", "+++ b/dry.txt", "@@ -1 +1 @@", "-missing", "+oops", ""])
    failed = tool_handlers["apply_patch"]({"path": "dry.txt", "patch": bad_patch})
    assert failed.get("error") is True


def test_batch(tool_handlers, sandbox: Path):
    (sandbox / "a.txt").write_text("a\n", encoding="utf8")
    (sandbox / "b.txt").write_text("b\n", encoding="utf8")
    patches = [
        "\n".join(["--- a/a.txt", "+++ b/a.txt", "@@ -1 +1 @@", "-a", "+aa", ""]),
        "\n".join(["--- a/b.txt", "+++ b/b.txt", "@@ -1 +1 @@", "-b", "+bb", ""]),
    ]
    dry = tool_handlers["apply_patch"]({"patches": [{"path": "a.txt", "patch": patches[0]}, {"path": "b.txt", "patch": patches[1]}], "dryRun": True})
    assert "Dry-run OK for 2 file(s)" in dry["output"]
    applied = tool_handlers["apply_patch"]({"patches": [{"path": "a.txt", "patch": patches[0]}, {"path": "b.txt", "patch": patches[1]}]})
    assert "Patched 2 file(s)" in applied["output"]
    assert (sandbox / "a.txt").read_text(encoding="utf8").strip() == "aa"
    assert (sandbox / "b.txt").read_text(encoding="utf8").strip() == "bb"
