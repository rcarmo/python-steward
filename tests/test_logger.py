"""Tests for logger module."""

from __future__ import annotations

from pathlib import Path


def test_logger_human_entry():
    from steward.logger import HumanEntry, Logger

    logger = Logger(
        provider="echo",
        model="test",
        enable_human_logs=False,
        enable_file_logs=False,
    )

    # Should not raise even with logs disabled
    logger.human(HumanEntry(title="test", body="content", variant="model"))


def test_logger_json_entry(sandbox: Path):
    from steward.logger import Logger

    log_file = sandbox / "log.json"
    logger = Logger(
        provider="echo",
        model="test",
        log_json_path=str(log_file),
        enable_human_logs=False,
        enable_file_logs=True,
    )

    logger.json({"type": "test", "data": "value"})

    assert log_file.exists()
    content = log_file.read_text()
    assert "test" in content


def test_logger_spinner():
    from steward.logger import Logger

    logger = Logger(
        provider="echo",
        model="test",
        enable_human_logs=False,
        enable_file_logs=False,
    )

    stop = logger.start_spinner()
    assert callable(stop)
    stop()  # Should not raise


def test_human_entry_variants():
    from steward.logger import HumanEntry

    for variant in ["model", "tool", "error", "warn", "todo"]:
        entry = HumanEntry(title="test", body="body", variant=variant)
        assert entry.variant == variant


def test_logger_with_pretty(sandbox: Path):
    from steward.logger import HumanEntry, Logger

    logger = Logger(provider="echo", model="test", enable_human_logs=True, enable_file_logs=False, pretty=True)

    # Should not raise
    logger.human(HumanEntry(title="test", body="content", variant="model"))


def test_logger_json_multiple_entries(sandbox: Path):
    from steward.logger import Logger

    log_file = sandbox / "multi.json"
    logger = Logger(
        provider="echo",
        model="test",
        log_json_path=str(log_file),
        enable_human_logs=False,
        enable_file_logs=True,
    )

    logger.json({"type": "first"})
    logger.json({"type": "second"})

    content = log_file.read_text()
    assert "first" in content
    assert "second" in content
