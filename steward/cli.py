"""CLI entrypoint for steward."""

from __future__ import annotations

import argparse
from os import chdir
from pathlib import Path
from typing import Optional, Union

from .config import ensure_dotenv_loaded, set_sandbox_root
from .runner import RunnerOptions, run_steward
from .session import generate_session_id


def parse_args() -> Union[RunnerOptions, dict]:
    """Parse CLI arguments. Returns RunnerOptions for single run, or dict with mode key for REPL."""
    # Load .env early before parsing args
    ensure_dotenv_loaded()

    parser = argparse.ArgumentParser(description="steward <prompt> [options]")
    parser.add_argument("prompt", nargs=argparse.REMAINDER, help="Prompt to run")
    parser.add_argument("--repl", action="store_true", help="Start interactive REPL mode")
    parser.add_argument("--provider", choices=["echo", "openai", "azure"], help="LLM provider (default: echo)")
    parser.add_argument("--model", help="Model name (default: gpt-4o-mini)")
    parser.add_argument("--max-steps", type=int, help="Limit tool/LLM turns (default: 16)")
    parser.add_argument("--timeout-ms", type=int, help="Per-LLM-call timeout in milliseconds")
    parser.add_argument("--retries", type=int, help="Retry failed/timeout LLM calls (default: 0)")
    parser.add_argument("--log-json", dest="log_json", help="Write JSON logs to file (default: .steward-log.jsonl)")
    parser.add_argument("--no-log-json", action="store_true", help="Disable JSONL logging")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable logs to stdout")
    parser.add_argument("--pretty", action="store_true", help="Enable pretty boxed/color human logs")
    parser.add_argument("--system", dest="system", help="Load system prompt from file")
    parser.add_argument(
        "--session",
        dest="session",
        nargs="?",
        const="auto",
        help="Enable session persistence (auto-generates ID if not specified)",
    )
    parser.add_argument("--instructions", dest="instructions", help="Load custom instructions from file")
    parser.add_argument(
        "--sandbox",
        nargs="?",
        const="sandbox",
        help="Run inside a sandbox directory (default: ./sandbox); creates it if missing",
    )
    parsed = parser.parse_args()

    # Handle sandbox before anything else
    if parsed.sandbox:
        sandbox_path = Path(parsed.sandbox).resolve()
        sandbox_path.mkdir(parents=True, exist_ok=True)
        set_sandbox_root(sandbox_path)
        chdir(sandbox_path)

    # Load system prompt if specified
    system_prompt: Optional[str] = None
    if parsed.system:
        system_path = Path(parsed.system).resolve()
        system_prompt = system_path.read_text(encoding="utf8")

    # Load custom instructions if specified
    custom_instructions: Optional[str] = None
    if parsed.instructions:
        instructions_path = Path(parsed.instructions).resolve()
        custom_instructions = instructions_path.read_text(encoding="utf8")

    # Handle session ID
    session_id: Optional[str] = None
    if parsed.session:
        session_id = parsed.session if parsed.session != "auto" else generate_session_id()

    # REPL mode (default when no prompt provided)
    prompt_text = " ".join(parsed.prompt).strip()
    if parsed.repl or not prompt_text:
        return {
            "repl": True,
            "provider": parsed.provider,
            "model": parsed.model,
            "max_steps": parsed.max_steps,
            "timeout_ms": parsed.timeout_ms,
            "retries": parsed.retries,
            "system_prompt": system_prompt,
            "custom_instructions": custom_instructions,
            "log_json_path": None if parsed.no_log_json else parsed.log_json,
            "enable_file_logs": not parsed.no_log_json,
            "quiet": parsed.quiet,
            "pretty": parsed.pretty,
            "session_id": session_id,
        }

    return RunnerOptions(
        prompt=prompt_text,
        provider=parsed.provider,
        model=parsed.model,
        max_steps=parsed.max_steps,
        request_timeout_ms=parsed.timeout_ms,
        retries=parsed.retries,
        system_prompt=system_prompt,
        log_json_path=None if parsed.no_log_json else parsed.log_json,
        enable_human_logs=not parsed.quiet,
        enable_file_logs=not parsed.no_log_json,
        pretty_logs=parsed.pretty,
        session_id=session_id,
        custom_instructions=custom_instructions,
    )


def main() -> None:
    result = parse_args()
    if isinstance(result, dict):
        if result.get("repl"):
            from .repl import run_repl

            run_repl(
                provider=result["provider"],
                model=result["model"],
                max_steps=result["max_steps"],
                timeout_ms=result["timeout_ms"],
                retries=result["retries"],
                system_prompt=result["system_prompt"],
                custom_instructions=result["custom_instructions"],
                log_json_path=result["log_json_path"],
                enable_file_logs=result["enable_file_logs"],
                quiet=result["quiet"],
                pretty=result["pretty"],
                session_id=result["session_id"],
            )
    else:
        run_steward(result)


if __name__ == "__main__":
    main()
