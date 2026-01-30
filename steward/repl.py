"""REPL mode for steward with full line editing capabilities."""

from __future__ import annotations

import atexit
import readline
from pathlib import Path
from sys import stderr, stdout
from typing import List, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from .config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, detect_provider, ensure_dotenv_loaded
from .runner import RunnerOptions, RunnerResult, run_steward_with_history
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
    enable_file_logs: bool = True,
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
    last_result: Optional[RunnerResult] = None

    if not quiet:
        print(f"Steward REPL (provider={effective_provider}, model={effective_model})")
        print("Commands: new (fresh conversation), stats (token count), clear, exit")
        print("")

    def _print_usage_summary(result: RunnerResult) -> None:
        if quiet or not result or not result.usage_summary:
            return
        usage = result.usage_summary
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        cached = usage.get("cached_tokens", 0)
        print("\nSession token stats:")
        print(f"  prompt: {prompt}, completion: {completion}, total: {total}")
        if cached:
            cache_pct = int(100 * cached / prompt) if prompt else 0
            print(f"  cached: {cached} ({cache_pct}% of prompt)")

    while True:
        prompt_text = read_input()

        if prompt_text is None:
            # EOF (Ctrl+D)
            if not quiet:
                print("\nGoodbye!")
                if last_result:
                    _print_usage_summary(last_result)
            break

        if not prompt_text.strip():
            # Empty input or cancelled
            continue

        # Special commands
        stripped = prompt_text.strip().lower()
        if stripped in ("exit", "quit", ":q"):
            if not quiet:
                print("Goodbye!")
                if last_result:
                    _print_usage_summary(last_result)
            break

        if stripped == "clear":
            print("\033[2J\033[H", end="", flush=True)
            continue

        if stripped == "new":
            conversation_history = None
            last_result = None
            if not quiet:
                print("Started new conversation.")
            continue

        if stripped == "stats":
            if conversation_history:
                try:
                    from .conversation import get_conversation_stats

                    stats = get_conversation_stats(conversation_history, effective_model)
                    print(f"Conversation: {stats['message_count']} messages, {stats['total_tokens']} tokens")
                    print(
                        f"  User: {stats['user_messages']}, Assistant: {stats['assistant_messages']}, Tool: {stats['tool_messages']}"
                    )
                except Exception:
                    print("Token stats unavailable (missing tiktoken).")
            else:
                print("No conversation history yet.")
            continue

        if stripped == "history":
            history_len = readline.get_current_history_length()
            for i in range(1, min(history_len + 1, 21)):
                idx = max(1, history_len - 20 + i)
                if idx <= history_len:
                    print(f"{idx}: {readline.get_history_item(idx)}")
            continue

        stream_console: Optional[Console] = None
        stream_live: Optional[Live] = None
        stream_buffer = ""

        def stream_handler(chunk: str, done: bool) -> None:
            nonlocal stream_console, stream_live, stream_buffer
            if quiet:
                return
            if not pretty:
                print(chunk, end="", flush=True)
                return
            if stream_console is None:
                stream_console = Console()
                stream_live = Live(Markdown("", justify="left"), console=stream_console, refresh_per_second=8)
                stream_live.start()
            if chunk:
                stream_buffer += chunk
                stream_live.update(Markdown(stream_buffer, justify="left"))
            if done and stream_live:
                stream_live.stop()

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
            stream_handler=stream_handler,
        )

        try:
            result = run_steward_with_history(options)
            last_result = result
            if pretty and not quiet and stream_live:
                stream_live.stop()
            if not pretty and not quiet:
                print("")
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
