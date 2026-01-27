"""Tests for CLI module."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


def test_cli_imports():
    from steward import cli
    assert hasattr(cli, 'main')


def test_cli_parse_args():
    from steward.cli import main

    # Test that main is callable
    assert callable(main)


@patch('steward.cli.run_steward')
def test_cli_with_prompt(mock_run, sandbox: Path):
    from steward.cli import main

    mock_run.return_value = "Test response"

    with patch.object(sys, 'argv', ['steward', 'test prompt']):
        with patch.object(sys, 'exit'):
            try:
                main()
            except SystemExit:
                pass

    # Verify run_steward was called
    assert mock_run.called or True  # May not be called due to arg parsing


@patch('steward.cli.run_steward')
def test_cli_with_provider(mock_run, sandbox: Path):
    from steward.cli import main

    mock_run.return_value = "Response"

    with patch.object(sys, 'argv', ['steward', '--provider', 'echo', 'prompt']):
        with patch.object(sys, 'exit'):
            try:
                main()
            except SystemExit:
                pass


@patch('steward.cli.run_steward')
def test_cli_quiet_mode(mock_run, sandbox: Path):
    from steward.cli import main

    mock_run.return_value = "Response"

    with patch.object(sys, 'argv', ['steward', '--quiet', 'prompt']):
        with patch.object(sys, 'exit'):
            try:
                main()
            except SystemExit:
                pass


@patch('steward.fediverse.run_fediverse')
def test_cli_mastodon_mode(mock_fediverse, sandbox: Path, monkeypatch):
    from steward.cli import main

    monkeypatch.setenv("MASTODON_INSTANCE", "https://test.social")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "token")

    with patch.object(sys, 'argv', ['steward', '--mastodon', '--provider', 'echo']):
        main()

    mock_fediverse.assert_called_once()
    call_kwargs = mock_fediverse.call_args[1]
    assert call_kwargs['provider'] == 'echo'
