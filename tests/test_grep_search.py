from __future__ import annotations

from pathlib import Path


def test_finds_matches(tool_handlers, sandbox: Path):
    (sandbox / "search.txt").write_text("hello world\nbye\n", encoding="utf8")
    result = tool_handlers["grep_search"]({"pattern": "hello"})
    assert "search.txt:1: hello world" in result["output"]


def test_filters_and_max_results(tool_handlers, sandbox: Path):
    (sandbox / "skip").mkdir()
    (sandbox / "keep").mkdir()
    (sandbox / "skip" / "hit.txt").write_text("hello\n", encoding="utf8")
    (sandbox / "keep" / "hit.txt").write_text("hello\n", encoding="utf8")
    result = tool_handlers["grep_search"]({"pattern": "hello", "excludePath": "skip", "maxResults": 1})
    assert "keep/hit.txt:1: hello" in result["output"]
    assert "skip/hit.txt" not in result["output"]
    lines = [line for line in result["output"].split("\n") if line.strip()]
    assert len(lines) == 1
    glob_result = tool_handlers["grep_search"]({"pattern": "hello", "includeGlob": "keep/**"})
    assert "keep/hit.txt:1: hello" in glob_result["output"]
    assert "skip/hit.txt" not in glob_result["output"]


def test_context_and_options(tool_handlers, sandbox: Path):
    (sandbox / ".hidden").mkdir()
    (sandbox / "sample.txt").write_text("one\nHello world\nthree\n", encoding="utf8")
    (sandbox / ".hidden" / "inside.txt").write_text("Hello hidden\n", encoding="utf8")
    ctx = tool_handlers["grep_search"]({"pattern": "hello", "smartCase": True, "contextLines": 1})
    assert "sample.txt:1: one" in ctx["output"]
    assert "sample.txt:2: Hello world" in ctx["output"]
    assert "sample.txt:3: three" in ctx["output"]
    fixed = tool_handlers["grep_search"]({"pattern": "Hello", "fixedString": True, "wordMatch": True, "caseSensitive": True})
    assert "sample.txt:2: Hello world" in fixed["output"]
    hidden = tool_handlers["grep_search"]({"pattern": "hidden", "includeHidden": True})
    assert ".hidden/inside.txt:1: Hello hidden" in hidden["output"]
    labeled = tool_handlers["grep_search"]({"pattern": "hello", "contextLines": 1, "withContextLabels": True})
    assert "M: Hello world" in labeled["output"]
    assert "C: one" in labeled["output"]
    maxed = tool_handlers["grep_search"]({"pattern": "x", "maxFileBytes": 1})
    assert maxed["output"] == "No matches"


def test_asymmetric_context(tool_handlers, sandbox: Path):
    (sandbox / "ctx.txt").write_text("zero\none\ntwo\nthree\nfour\n", encoding="utf8")
    result = tool_handlers["grep_search"]({"pattern": "one|three", "regex": True, "beforeContext": 1, "afterContext": 0, "withContextSeparators": True})
    lines = [line for line in result["output"].split("\n") if line.strip()]
    assert "ctx.txt:1: zero" in lines[0]
    assert "ctx.txt:2: one" in lines[1]
    assert lines[2] == "--"
    assert "ctx.txt:3: two" in lines[3]
    assert "ctx.txt:4: three" in lines[4]


def test_headings_and_counts(tool_handlers, sandbox: Path):
    (sandbox / "f1.txt").write_text("hit one\nmiss\n", encoding="utf8")
    (sandbox / "f2.txt").write_text("hit two\nhit three\n", encoding="utf8")
    result = tool_handlers["grep_search"]({"pattern": "hit", "withHeadings": True, "withCounts": True})
    assert "f1.txt (1 match)" in result["output"]
    assert "f2.txt (2 matches)" in result["output"]
    assert "f1.txt:1:" in result["output"]
    assert "f2.txt:1:" in result["output"]


def test_env_default_max_results(tool_handlers, sandbox: Path, monkeypatch):
    monkeypatch.setenv("STEWARD_SEARCH_MAX_RESULTS", "1")
    (sandbox / "a.txt").write_text("hello\nhello\n", encoding="utf8")
    (sandbox / "b.txt").write_text("hello\n", encoding="utf8")
    result = tool_handlers["grep_search"]({"pattern": "hello"})
    lines = [line for line in result["output"].split("\n") if line.strip()]
    assert len(lines) == 1
