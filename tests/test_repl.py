"""Tests for REPL module."""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch


def test_repl_imports():
    from steward import repl
    assert hasattr(repl, 'run_repl')
    assert hasattr(repl, 'main')
    assert hasattr(repl, 'setup_readline')
    assert hasattr(repl, 'read_input')


def test_setup_readline(tmp_path: Path):
    from steward.repl import setup_readline

    with patch('steward.repl.HISTORY_DIR', tmp_path):
        with patch('steward.repl.HISTORY_FILE', tmp_path / 'history'):
            setup_readline()
            # Should not raise


def test_read_input_simple():
    from steward.repl import read_input

    with patch('builtins.input', return_value='hello world'):
        result = read_input()
        assert result == 'hello world'


def test_read_input_multiline():
    from steward.repl import read_input

    inputs = iter(['line one\\', 'line two'])
    with patch('builtins.input', side_effect=lambda _: next(inputs)):
        result = read_input()
        assert result == 'line one\nline two'


def test_read_input_eof():
    from steward.repl import read_input

    with patch('builtins.input', side_effect=EOFError):
        result = read_input()
        assert result is None


def test_read_input_keyboard_interrupt():
    from steward.repl import read_input

    with patch('builtins.input', side_effect=KeyboardInterrupt):
        with patch('sys.stdout', new_callable=StringIO):
            result = read_input()
            assert result == ''


def test_run_repl_exit_command():
    from steward.repl import run_repl

    inputs = iter(['exit'])
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)
                # Should exit cleanly


def test_run_repl_quit_command():
    from steward.repl import run_repl

    inputs = iter(['quit'])
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)


def test_run_repl_colon_q_command():
    from steward.repl import run_repl

    inputs = iter([':q'])
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)


def test_run_repl_clear_command():
    from steward.repl import run_repl

    inputs = iter(['clear', 'exit'])
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            stdout = StringIO()
            with patch('sys.stdout', stdout):
                run_repl(quiet=True)
            # Clear sends ANSI escape
            assert '\033[2J' in stdout.getvalue()


def test_run_repl_history_command():
    from steward.repl import run_repl

    inputs = iter(['history', 'exit'])
    with patch('steward.repl.setup_readline'):
        with patch('readline.get_current_history_length', return_value=0):
            with patch('builtins.input', side_effect=lambda _: next(inputs)):
                with patch('sys.stdout', new_callable=StringIO):
                    run_repl(quiet=True)


def test_run_repl_eof_exit():
    from steward.repl import run_repl

    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=EOFError):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)


def test_run_repl_empty_input_continues():
    from steward.repl import run_repl

    inputs = iter(['', '   ', 'exit'])
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)


@patch('steward.repl.run_steward')
def test_run_repl_executes_prompt(mock_run_steward):
    from steward.repl import run_repl

    inputs = iter(['hello world', 'exit'])
    mock_run_steward.return_value = 'response'

    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                run_repl(quiet=True)

    assert mock_run_steward.called
    call_args = mock_run_steward.call_args[0][0]
    assert call_args.prompt == 'hello world'


@patch('steward.repl.run_steward')
def test_run_repl_handles_error(mock_run_steward):
    from steward.repl import run_repl

    inputs = iter(['test prompt', 'exit'])
    mock_run_steward.side_effect = Exception('Test error')

    stderr_capture = StringIO()
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            with patch('sys.stdout', new_callable=StringIO):
                with patch('steward.repl.stderr', stderr_capture):
                    run_repl(quiet=True)

    assert 'Error: Test error' in stderr_capture.getvalue()


def test_run_repl_banner_shown():
    from steward.repl import run_repl

    inputs = iter(['exit'])
    with patch('steward.repl.setup_readline'):
        with patch('builtins.input', side_effect=lambda _: next(inputs)):
            stdout = StringIO()
            with patch('sys.stdout', stdout):
                run_repl(quiet=False)

    output = stdout.getvalue()
    assert 'Steward REPL' in output
    assert 'Ctrl+D' in output


def test_main_function():
    from steward.repl import main

    with patch('steward.repl.run_repl') as mock_run:
        with patch.object(sys, 'argv', ['steward-repl']):
            main()
            assert mock_run.called


def test_cli_repl_flag():
    from steward.cli import parse_args

    with patch.object(sys, 'argv', ['steward', '--repl']):
        result = parse_args()
        assert isinstance(result, dict)
        assert result['repl'] is True


def test_cli_repl_with_provider():
    from steward.cli import parse_args

    with patch.object(sys, 'argv', ['steward', '--repl', '--provider', 'openai']):
        result = parse_args()
        assert isinstance(result, dict)
        assert result['repl'] is True
        assert result['provider'] == 'openai'
