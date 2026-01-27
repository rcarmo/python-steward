"""Tests for REPL module."""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def repl_patches():
    with patch('steward.repl.setup_readline'):
        yield


@pytest.mark.parametrize("attr", ["run_repl", "main", "setup_readline", "read_input"])
def test_repl_imports(attr):
    from steward import repl
    assert hasattr(repl, attr)


def test_setup_readline(tmp_path: Path):
    from steward.repl import setup_readline

    with patch('steward.repl.HISTORY_DIR', tmp_path):
        with patch('steward.repl.HISTORY_FILE', tmp_path / 'history'):
            setup_readline()


@pytest.mark.parametrize("inputs,expected", [
    (['hello world'], 'hello world'),
    (['line one\\', 'line two'], 'line one\nline two'),
])
def test_read_input_variants(inputs, expected):
    from steward.repl import read_input

    input_iter = iter(inputs)
    with patch('builtins.input', side_effect=lambda _: next(input_iter)):
        result = read_input()
        assert result == expected


@pytest.mark.parametrize("side_effect,expected", [
    (EOFError, None),
    (KeyboardInterrupt, ''),
])
def test_read_input_exceptions(side_effect, expected):
    from steward.repl import read_input

    with patch('builtins.input', side_effect=side_effect):
        with patch('sys.stdout', new_callable=StringIO):
            result = read_input()
            assert result == expected


@pytest.mark.parametrize("commands,assert_fn", [
    (['exit'], None),
    (['quit'], None),
    ([":q"], None),
    (['clear', 'exit'], lambda out: '\033[2J' in out),
])
def test_run_repl_basic_commands(repl_patches, commands, assert_fn):
    from steward.repl import run_repl

    inputs = iter(commands)
    stdout = StringIO()
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        with patch('sys.stdout', stdout):
            run_repl(quiet=True)

    if assert_fn:
        assert assert_fn(stdout.getvalue())


def test_run_repl_history_command(repl_patches):
    from steward.repl import run_repl

    inputs = iter(['history', 'exit'])
    with patch('readline.get_current_history_length', return_value=0):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)


def test_run_repl_new_command_resets_history(repl_patches):
    from steward.repl import run_repl
    from steward.runner import RunnerResult

    inputs = iter(['hello', 'new', 'hello again', 'exit'])

    with patch('steward.repl.run_steward_with_history') as mock_run:
        mock_run.return_value = RunnerResult(response='ok', messages=[{'role': 'user', 'content': 'hello'}])
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)

    assert mock_run.call_count >= 2


def test_run_repl_stats_no_history(repl_patches):
    from steward.repl import run_repl

    inputs = iter(['stats', 'exit'])
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        stdout = StringIO()
        with patch('sys.stdout', stdout):
            run_repl(quiet=False)

    assert 'No conversation history' in stdout.getvalue()


def test_run_repl_eof_exit(repl_patches):
    from steward.repl import run_repl

    with patch('builtins.input', side_effect=EOFError):
        with patch('sys.stdout', new_callable=StringIO):
            run_repl(quiet=True)


def test_run_repl_empty_input_continues(repl_patches):
    from steward.repl import run_repl

    inputs = iter(['', '   ', 'exit'])
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        with patch('sys.stdout', new_callable=StringIO):
            run_repl(quiet=True)


@patch('steward.repl.run_steward_with_history')
def test_run_repl_executes_prompt(mock_run_steward, repl_patches):
    from steward.repl import run_repl
    from steward.runner import RunnerResult

    inputs = iter(['hello world', 'exit'])
    mock_run_steward.return_value = RunnerResult(response='response', messages=[])

    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        with patch('sys.stdout', new_callable=StringIO):
            run_repl(quiet=True)

    assert mock_run_steward.called
    call_args = mock_run_steward.call_args[0][0]
    assert call_args.prompt == 'hello world'
    assert callable(call_args.stream_handler)


@patch('steward.repl.run_steward_with_history')
def test_run_repl_handles_error(mock_run_steward, repl_patches):
    from steward.repl import run_repl

    inputs = iter(['test prompt', 'exit'])
    mock_run_steward.side_effect = Exception('Test error')

    stderr_capture = StringIO()
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        with patch('sys.stdout', new_callable=StringIO):
            with patch('steward.repl.stderr', stderr_capture):
                run_repl(quiet=True)

    assert 'Error: Test error' in stderr_capture.getvalue()


def test_run_repl_banner_shown(repl_patches):
    from steward.repl import run_repl

    inputs = iter(['exit'])
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        stdout = StringIO()
        with patch('sys.stdout', stdout):
            run_repl(quiet=False)

    output = stdout.getvalue()
    assert 'Steward REPL' in output
    assert 'Commands:' in output


def test_run_repl_streams_markdown(repl_patches):
    from steward.repl import run_repl
    from steward.runner import RunnerResult

    inputs = iter(['stream test', 'exit'])
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        with patch('steward.repl.run_steward_with_history') as mock_run:
            def fake_run(opts):
                opts.stream_handler("**Hello", False)
                opts.stream_handler(" World**", True)
                return RunnerResult(response="**Hello World**", messages=[])
            mock_run.side_effect = fake_run
            with patch('steward.repl.Live') as mock_live:
                with patch('steward.repl.Markdown'):
                    with patch('sys.stdout', new_callable=StringIO):
                        run_repl(quiet=False, pretty=True)
            assert mock_live.return_value.start.called
            assert mock_live.return_value.update.called
            assert mock_live.return_value.stop.called


def test_main_function():
    from steward.repl import main

    with patch('steward.repl.run_repl') as mock_run:
        with patch.object(sys, 'argv', ['steward-repl']):
            main()
            assert mock_run.called


def test_cli_repl_flags():
    from steward.cli import parse_args

    with patch.object(sys, 'argv', ['steward', '--repl']):
        result = parse_args()
        assert isinstance(result, dict)
        assert result['repl'] is True

    with patch.object(sys, 'argv', ['steward', '--repl', '--provider', 'openai']):
        result = parse_args()
        assert isinstance(result, dict)
        assert result['repl'] is True
