"""Configuration helpers and defaults."""
from __future__ import annotations

from os import getenv
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_PROVIDER = "echo"
DEFAULT_MAX_STEPS = 32
DEFAULT_REQUEST_TIMEOUT_MS: Optional[int] = None

# Track if we've loaded .env
_dotenv_loaded = False


def ensure_dotenv_loaded() -> None:
    """Load .env file from current directory if not already loaded."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return

    # Try to load from current directory
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Also try parent directories up to home
        for parent in Path.cwd().parents:
            env_file = parent / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                break
            if parent == Path.home():
                break

    _dotenv_loaded = True


def detect_provider() -> str:
    """Autodetect provider based on available environment variables."""
    ensure_dotenv_loaded()

    # Check Azure first (more specific)
    azure_endpoint = getenv("STEWARD_AZURE_OPENAI_ENDPOINT") or getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = getenv("STEWARD_AZURE_OPENAI_KEY") or getenv("AZURE_OPENAI_KEY")
    azure_deployment = getenv("STEWARD_AZURE_OPENAI_DEPLOYMENT") or getenv("AZURE_OPENAI_DEPLOYMENT")
    if azure_endpoint and azure_key and azure_deployment:
        return "azure"

    # Check OpenAI
    openai_key = getenv("STEWARD_OPENAI_API_KEY") or getenv("OPENAI_API_KEY")
    if openai_key:
        return "openai"

    # Fallback to echo
    return "echo"


def env_int(name: str, fallback: int) -> int:
    raw = getenv(name)
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    return value if value > 0 else fallback


def env_list(name: str) -> list[str]:
    raw = getenv(name, "")
    parts = [part.strip() for part in raw.split(",")]
    return [part for part in parts if part]
