"""Tests for config module."""
from __future__ import annotations

import pytest


def test_env_int_valid(monkeypatch):
    from steward.config import env_int

    monkeypatch.setenv("TEST_INT", "42")
    assert env_int("TEST_INT", 0) == 42


def test_env_int_missing():
    from steward.config import env_int

    assert env_int("NONEXISTENT_VAR", 99) == 99


def test_env_int_invalid(monkeypatch):
    from steward.config import env_int

    monkeypatch.setenv("TEST_INT", "not_a_number")
    assert env_int("TEST_INT", 10) == 10


def test_env_int_negative(monkeypatch):
    from steward.config import env_int

    monkeypatch.setenv("TEST_INT", "-5")
    assert env_int("TEST_INT", 10) == 10  # Negative returns fallback


def test_env_list(monkeypatch):
    from steward.config import env_list

    monkeypatch.setenv("TEST_LIST", "a,b,c")
    result = env_list("TEST_LIST")
    assert result == ["a", "b", "c"]


def test_env_list_empty():
    from steward.config import env_list

    result = env_list("NONEXISTENT_VAR")
    assert result == []


def test_env_list_with_spaces(monkeypatch):
    from steward.config import env_list

    monkeypatch.setenv("TEST_LIST", "a , b , c")
    result = env_list("TEST_LIST")
    assert result == ["a", "b", "c"]


def test_detect_provider_azure(monkeypatch):
    from steward.config import detect_provider

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    assert detect_provider() == "azure"


def test_detect_provider_azure_steward_prefix(monkeypatch):
    from steward.config import detect_provider

    monkeypatch.setenv("STEWARD_AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("STEWARD_AZURE_OPENAI_KEY", "test-key")
    monkeypatch.setenv("STEWARD_AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    assert detect_provider() == "azure"


def test_detect_provider_openai(monkeypatch):
    from steward.config import detect_provider

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    assert detect_provider() == "openai"


def test_detect_provider_openai_steward_prefix(monkeypatch):
    from steward.config import detect_provider

    monkeypatch.setenv("STEWARD_OPENAI_API_KEY", "sk-test-key")
    assert detect_provider() == "openai"


def test_detect_provider_fallback_echo(monkeypatch):
    from steward.config import detect_provider

    # Clear any provider env vars
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STEWARD_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    monkeypatch.delenv("STEWARD_AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("STEWARD_AZURE_OPENAI_KEY", raising=False)
    monkeypatch.delenv("STEWARD_AZURE_OPENAI_DEPLOYMENT", raising=False)
    assert detect_provider() == "echo"


def test_detect_provider_azure_incomplete(monkeypatch):
    from steward.config import detect_provider

    # Only endpoint and key, no deployment - should not detect azure
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_KEY", "test-key")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STEWARD_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STEWARD_AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("STEWARD_AZURE_OPENAI_KEY", raising=False)
    monkeypatch.delenv("STEWARD_AZURE_OPENAI_DEPLOYMENT", raising=False)
    assert detect_provider() == "echo"


@pytest.mark.parametrize("model,expected", [
    ("o1-mini", True),
    ("o1-preview", True),
    ("o3-mini", True),
    ("o4-mini", True),
    ("gpt-5-mini", True),
    ("gpt-5", True),
    ("gpt-4o", False),  # 4o is not o-series, it's GPT-4 Omni
    ("gpt-4-turbo", False),
    ("gpt-3.5-turbo", False),
    ("claude-3-opus", False),
    ("my-custom-o1-deployment", True),  # Azure custom name with o1
])
def test_is_o_series_model(model, expected):
    from steward.config import is_o_series_model

    assert is_o_series_model(model) == expected


@pytest.mark.parametrize("model,expected_role", [
    ("o1-mini", "developer"),
    ("gpt-5-mini", "developer"),
    ("gpt-4-turbo", "system"),
    ("gpt-3.5-turbo", "system"),
    ("claude-3-opus", "system"),
])
def test_get_system_role(model, expected_role):
    from steward.config import get_system_role

    assert get_system_role(model) == expected_role
