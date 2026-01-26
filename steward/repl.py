"""REPL mode for steward with full line editing capabilities."""
from __future__ import annotations

import atexit
import readline
from pathlib import Path
from sys import stderr, stdout
from typing import List, Optional

from .config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, detect_provider, ensure_dotenv_loaded
from .runner import RunnerOptions, run_steward_with_history
from .session import generate_session_id
from .types import Message

# History file location
HISTORY_DIR = Path.home() / ".steward"
HISTORY_FILE = HISTORY_DIR / "history"
MAX_HISTORY_LENGTH = 1000

# REPL prompt
PROMPT = "steward> "
CONTINUATION_PROMPT = "....... "


def setup_readline() -> None:
    """Configure readline with history and editing capabilities."""
    # Enable tab completion (no-op completer for now)
    readline.parse_and_bind("tab: complete")

    # Enable common editing bindings
    readline.parse_and_bind("set editing-mode emacs")
    readline.parse_and_bind("set show-all-if-ambiguous on")

    # Load history if it exists
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if HISTORY_FILE.exists():
        try:
            readline.read_history_file(str(HISTORY_FILE))
        except (OSError, IOError):
            pass

    # Set history length
    readline.set_history_length(MAX_HISTORY_LENGTH)

    # Save history on exit
    atexit.register(save_history)


def save_history() -> None:
    """Save readline history to file."""
    try:
        readline.write_history_file(str(HISTORY_FILE))
    except (OSError, IOError):
        pass


def read_input() -> Optional[str]:
    """Read input with support for multi-line continuation (trailing backslash)."""
    lines = []
    prompt = PROMPT

    while True:
        try:
            line = input(prompt)
        except EOFError:
            if lines:
                # Return partial input on Ctrl+D mid-input
                return "\n".join(lines)
            return None
        except KeyboardInterrupt:
            # Ctrl+C cancels current input
            print("", file=stdout)
            return ""

        if line.endswith("\\"):
            lines.append(line[:-1])
            prompt = CONTINUATION_PROMPT
        else:
            lines.append(line)
            break

    return "\n".join(lines)


def run_repl(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_steps: Optional[int] = None,
    timeout_ms: Optional[int] = None,
    retries: Optional[int] = None,
    system_prompt: Optional[str] = None,
    custom_instructions: Optional[str] = None,
    log_json_path: Optional[str] = None,
    enable_file_logs: bool = False,
    quiet: bool = False,
    pretty: bool = True,
    session_id: Optional[str] = None,
) -> None:
    """Run the REPL loop."""
    # Load .env early
    ensure_dotenv_loaded()
    setup_readline()

    # Generate session ID if not provided (REPL typically wants persistence)
    if session_id is None:
        session_id = generate_session_id()

    effective_provider = provider or detect_provider()
    effective_model = model or DEFAULT_MODEL

    # Conversation history for multi-turn
    conversation_history: Optional[List[Message]] = None

    if not quiet:
        print(f"Steward REPL (provider={effective_provider}, model={effective_model})")
        print("Type your prompts. Use Ctrl+D to exit, Ctrl+C to cancel input.")
        print("End a line with \\ for multi-line input. Type 'new' to start fresh conversation.")
        print("")

    while True:
        prompt_text = read_input()

        if prompt_text is None:
            # EOF (Ctrl+D)
            if not quiet:
                print("\nGoodbye!")
            break

        if not prompt_text.strip():
            # Empty input or cancelled
            continue

        # Special commands
        stripped = prompt_text.strip().lower()
        if stripped in ("exit", "quit", ":q"):
            if not quiet:
                print("Goodbye!")
            break

        if stripped == "clear":
            print("\033[2J\033[H", end="", flush=True)
            continue

        if stripped == "new":
            conversation_history = None
            if not quiet:
                print("Started new conversation.")
            continue

        if stripped == "history":
            history_len = readline.get_current_history_length()
            for i in range(1, min(history_len + 1, 21)):
                idx = max(1, history_len - 20 + i)
                if idx <= history_len:
                    print(f"{idx}: {readline.get_history_item(idx)}")
            continue

        # Run steward with the prompt
        options = RunnerOptions(
            prompt=prompt_text,
            provider=provider,
            model=model,
            max_steps=max_steps or DEFAULT_MAX_STEPS,
            request_timeout_ms=timeout_ms,
            retries=retries,
            system_prompt=system_prompt,
            log_json_path=log_json_path,
            enable_human_logs=not quiet,
            enable_file_logs=enable_file_logs,
            pretty_logs=pretty,
            compact_logs=True,  # Use abbreviated logging in REPL
            session_id=session_id,
            custom_instructions=custom_instructions,
            conversation_history=conversation_history,
        )

        try:
            result = run_steward_with_history(options)
            # Update conversation history for next turn
            conversation_history = result.messages
        except Exception as err:
            print(f"Error: {err}", file=stderr)

        # Print blank line between interactions
        if not quiet:
            print("")


def main() -> None:
    """Direct entrypoint for steward-repl command."""
    import argparse

    parser = argparse.ArgumentParser(description="Steward interactive REPL")
    parser.add_argument("--provider", choices=["echo", "openai", "azure"], help="LLM provider (default: echo)")
    parser.add_argument("--model", help="Model name (default: gpt-4o-mini)")
    parser.add_argument("--max-steps", type=int, help="Limit tool/LLM turns (default: 32)")
    parser.add_argument("--timeout-ms", type=int, help="Per-LLM-call timeout in milliseconds")
    parser.add_argument("--retries", type=int, help="Retry failed/timeout LLM calls (default: 0)")
    parser.add_argument("--log-json", dest="log_json", help="Write JSON logs to file")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable logs to stdout")
    parser.add_argument("--pretty", action="store_true", default=True, help="Enable pretty boxed/color human logs")
    parser.add_argument("--system", dest="system", help="Load system prompt from file")
    parser.add_argument("--session", dest="session", help="Session ID for persistence")
    parser.add_argument("--instructions", dest="instructions", help="Load custom instructions from file")
    parsed = parser.parse_args()

    system_prompt = None
    if parsed.system:
        system_prompt = Path(parsed.system).resolve().read_text(encoding="utf8")

    custom_instructions = None
    if parsed.instructions:
        custom_instructions = Path(parsed.instructions).resolve().read_text(encoding="utf8")

    run_repl(
        provider=parsed.provider,
        model=parsed.model,
        max_steps=parsed.max_steps,
        timeout_ms=parsed.timeout_ms,
        retries=parsed.retries,
        system_prompt=system_prompt,
        custom_instructions=custom_instructions,
        log_json_path=parsed.log_json,
        enable_file_logs=bool(parsed.log_json),
        quiet=parsed.quiet,
        pretty=parsed.pretty,
        session_id=parsed.session,
    )


if __name__ == "__main__":
    main()
