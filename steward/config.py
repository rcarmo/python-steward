"""Configuration helpers and defaults."""
from __future__ import annotations

from os import getenv
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROVIDER = "echo"
DEFAULT_MAX_STEPS = 32
DEFAULT_REQUEST_TIMEOUT_MS: Optional[int] = None

# Tool output limits (Codex-style truncation for context efficiency)
DEFAULT_TOOL_OUTPUT_LIMIT = 8000  # chars - prevents context blowup
DEFAULT_BASH_OUTPUT_LIMIT = 16000  # bash can be more verbose

# Track if we've loaded .env
_dotenv_loaded = False

# Sandbox root - when set, all file operations are restricted to this directory
_sandbox_root: Optional[Path] = None


def set_sandbox_root(path: Optional[Path]) -> None:
    """Set the sandbox root directory. All file operations will be restricted to this path."""
    global _sandbox_root
    _sandbox_root = path.resolve() if path else None


def get_sandbox_root() -> Optional[Path]:
    """Get the current sandbox root, or None if not sandboxed."""
    return _sandbox_root


def is_sandboxed() -> bool:
    """Check if sandbox mode is active."""
    return _sandbox_root is not None


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


def is_o_series_model(model: str) -> bool:
    """Check if model is an o-series (reasoning) model that uses developer role.

    O-series models (o1, o3, o4, etc.) use 'developer' role instead of 'system'.
    This includes Azure deployments that may have custom names but contain 'o1', 'o3', etc.
    """
    model_lower = model.lower()
    # Match o1, o3, o4 patterns (standalone or with suffixes like o1-mini, o4-mini)
    # Also match gpt-5 series which uses developer role
    o_patterns = ("o1", "o3", "o4", "gpt-5")
    for pattern in o_patterns:
        if pattern in model_lower:
            return True
    return False


def get_system_role(model: str) -> str:
    """Get the appropriate role for system instructions based on model.

    Returns 'developer' for o-series models, 'system' for others.
    """
    return "developer" if is_o_series_model(model) else "system"
