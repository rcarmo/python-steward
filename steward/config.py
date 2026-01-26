"""Configuration helpers and defaults."""
from __future__ import annotations

from os import getenv
from typing import Optional

from dotenv import load_dotenv

# Load .env file from current directory (if present)
load_dotenv()

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_PROVIDER = "echo"
DEFAULT_MAX_STEPS = 32
DEFAULT_REQUEST_TIMEOUT_MS: Optional[int] = None


def detect_provider() -> str:
    """Autodetect provider based on available environment variables."""
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
