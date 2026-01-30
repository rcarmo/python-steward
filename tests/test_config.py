"""Tests for config module."""

import pytest

PROVIDER_ENV_VARS = [
    "OPENAI_API_KEY",
    "STEWARD_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_DEPLOYMENT",
    "STEWARD_AZURE_OPENAI_ENDPOINT",
    "STEWARD_AZURE_OPENAI_KEY",
    "STEWARD_AZURE_OPENAI_DEPLOYMENT",
]


@pytest.fixture()
def clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for var in PROVIDER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.mark.parametrize(
    "value,fallback,expected",
    [
        ("42", 0, 42),
        ("not_a_number", 10, 10),
        ("-5", 10, 10),
        (None, 99, 99),
    ],
)
def test_env_int_cases(monkeypatch, value, fallback, expected):
    from steward.config import env_int

    if value is None:
        monkeypatch.delenv("TEST_INT", raising=False)
    else:
        monkeypatch.setenv("TEST_INT", value)
    assert env_int("TEST_INT", fallback) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("a,b,c", ["a", "b", "c"]),
        ("a , b , c", ["a", "b", "c"]),
        (None, []),
    ],
)
def test_env_list_cases(monkeypatch, value, expected):
    from steward.config import env_list

    if value is None:
        monkeypatch.delenv("TEST_LIST", raising=False)
    else:
        monkeypatch.setenv("TEST_LIST", value)
    assert env_list("TEST_LIST") == expected


@pytest.mark.parametrize(
    "envs,expected",
    [
        (
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_KEY": "test-key",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4",
            },
            "azure",
        ),
        (
            {
                "STEWARD_AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "STEWARD_AZURE_OPENAI_KEY": "test-key",
                "STEWARD_AZURE_OPENAI_DEPLOYMENT": "gpt-4",
            },
            "azure",
        ),
        ({"OPENAI_API_KEY": "sk-test-key"}, "openai"),
        ({"STEWARD_OPENAI_API_KEY": "sk-test-key"}, "openai"),
        ({}, "echo"),
        (
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_KEY": "test-key",
            },
            "echo",
        ),
    ],
)
def test_detect_provider_variants(clear_provider_env, monkeypatch, envs, expected):
    from steward.config import detect_provider

    for key, value in envs.items():
        monkeypatch.setenv(key, value)
    assert detect_provider() == expected


@pytest.mark.parametrize(
    "model,expected",
    [
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
    ],
)
def test_is_o_series_model(model, expected):
    from steward.config import is_o_series_model

    assert is_o_series_model(model) == expected


@pytest.mark.parametrize(
    "model,expected_role",
    [
        ("o1-mini", "developer"),
        ("gpt-5-mini", "developer"),
        ("gpt-4-turbo", "system"),
        ("gpt-3.5-turbo", "system"),
        ("claude-3-opus", "system"),
    ],
)
def test_get_system_role(model, expected_role):
    from steward.config import get_system_role

    assert get_system_role(model) == expected_role
