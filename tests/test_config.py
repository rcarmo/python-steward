"""Tests for config module."""
from __future__ import annotations


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
