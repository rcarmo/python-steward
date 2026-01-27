"""Tests for fediverse integration."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from steward.fediverse import (
    _extract_prompt,
    _is_too_old,
    _load_replied,
    _parse_timestamp,
    _save_replied,
    _truncate_for_toot,
)


@pytest.mark.parametrize("content,expected", [
    ("<p>@steward do something</p>", "do something"),
    ("<p><span class=\"h-card\">@steward</span> hello world</p>", "hello world"),
    ("@bot @steward multiple mentions test", "multiple mentions test"),
    ("<p>@steward</p><p>multi line</p>", "multi line"),
    ("plain text prompt", "plain text prompt"),
])
def test_extract_prompt(content, expected):
    result = _extract_prompt(content)
    assert result == expected


@pytest.mark.parametrize("text,max_chars,expected_len", [
    ("short", 480, 5),
    ("x" * 500, 480, 480),
    ("word " * 100, 100, 100),
])
def test_truncate_for_toot(text, max_chars, expected_len):
    result = _truncate_for_toot(text, max_chars)
    assert len(result) <= expected_len
    if len(text) > max_chars:
        assert result.endswith("...")


def test_load_replied_missing_file(sandbox: Path):
    result = _load_replied()
    assert result == set()


def test_save_and_load_replied(sandbox: Path):
    replied = {"123", "456", "789"}
    _save_replied(replied)
    loaded = _load_replied()
    assert loaded == replied


def test_load_replied_corrupt_json(sandbox: Path):
    Path(".steward-fediverse-replied.json").write_text("not valid json", encoding="utf8")
    result = _load_replied()
    assert result == set()


def test_parse_timestamp():
    ts = "2026-01-27T10:30:00Z"
    result = _parse_timestamp(ts)
    assert result.year == 2026
    assert result.month == 1
    assert result.day == 27


def test_is_too_old():
    # Recent timestamp should not be too old
    recent = datetime.now(UTC).isoformat()
    assert _is_too_old(recent, 24) is False

    # Old timestamp should be too old
    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    assert _is_too_old(old, 24) is True

    # Invalid timestamp should not be skipped
    assert _is_too_old("invalid", 24) is False


class MockResponse:
    """Mock aiohttp response."""
    def __init__(self, data, status=200):
        self._data = data
        self.status = status

    async def json(self):
        return self._data

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"HTTP {self.status}")


class MockClientSession:
    """Mock aiohttp ClientSession for testing."""
    def __init__(self, responses=None):
        self._responses = responses or []
        self._call_index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def get(self, *args, **kwargs):
        return self._make_context_manager("get", args, kwargs)

    def post(self, *args, **kwargs):
        return self._make_context_manager("post", args, kwargs)

    def _make_context_manager(self, method, args, kwargs):
        response = self._responses[self._call_index] if self._call_index < len(self._responses) else MockResponse({})
        self._call_index += 1

        class CM:
            async def __aenter__(cm_self):
                return response
            async def __aexit__(cm_self, *args):
                pass

        return CM()


@pytest.mark.asyncio
async def test_fetch_mentions(monkeypatch):
    from steward.fediverse import _fetch_mentions

    notifications = [
        {"id": "1", "type": "mention", "status": {"id": "100", "content": "test"}},
    ]
    mock_session = MockClientSession([MockResponse(notifications)])

    result = await _fetch_mentions(mock_session, "https://example.social", "token123")
    assert len(result) == 1
    assert result[0]["id"] == "1"


@pytest.mark.asyncio
async def test_get_status():
    from steward.fediverse import _get_status

    status_data = {"id": "100", "content": "test content"}
    mock_session = MockClientSession([MockResponse(status_data)])

    result = await _get_status(mock_session, "https://example.social", "token123", "100")
    assert result["id"] == "100"


@pytest.mark.asyncio
async def test_post_reply(monkeypatch):
    from steward.fediverse import _post_reply

    posted = MockResponse({"id": "200", "content": "reply"})
    mock_session = MockClientSession([posted])

    result = await _post_reply(
        mock_session, "https://example.social", "token123",
        in_reply_to_id="100", content="@user test reply"
    )
    assert result["id"] == "200"


def test_get_config_missing_instance(monkeypatch):
    from steward.fediverse import _get_config

    monkeypatch.delenv("MASTODON_INSTANCE", raising=False)
    monkeypatch.delenv("MASTODON_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="MASTODON_INSTANCE"):
        _get_config()


def test_get_config_missing_token(monkeypatch):
    from steward.fediverse import _get_config

    monkeypatch.setenv("MASTODON_INSTANCE", "https://example.social")
    monkeypatch.delenv("MASTODON_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="MASTODON_ACCESS_TOKEN"):
        _get_config()


def test_get_config_success(monkeypatch):
    from steward.fediverse import _get_config

    monkeypatch.setenv("MASTODON_INSTANCE", "example.social")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "token123")
    monkeypatch.setenv("MASTODON_POLL_INTERVAL", "30")
    monkeypatch.setenv("MASTODON_MAX_AGE_HOURS", "12")

    instance, token, interval, max_age = _get_config()
    assert instance == "https://example.social"
    assert token == "token123"
    assert interval == 30
    assert max_age == 12


def test_get_config_with_https_prefix(monkeypatch):
    from steward.fediverse import _get_config

    monkeypatch.setenv("MASTODON_INSTANCE", "https://example.social/")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "token123")

    instance, token, interval, max_age = _get_config()
    assert instance == "https://example.social"
    assert interval == 60  # default
    assert max_age == 24  # default


def test_get_config_default_interval(monkeypatch):
    from steward.fediverse import _get_config

    monkeypatch.setenv("MASTODON_INSTANCE", "test.social")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "token")
    monkeypatch.delenv("MASTODON_POLL_INTERVAL", raising=False)
    monkeypatch.delenv("MASTODON_MAX_AGE_HOURS", raising=False)

    instance, token, interval, max_age = _get_config()
    assert interval == 60
    assert max_age == 24


@pytest.mark.asyncio
async def test_process_mention_empty_prompt(sandbox: Path):
    from steward.fediverse import _process_mention

    notification = {
        "account": {"acct": "testuser"},
        "status": {"id": "100", "content": "<p>@steward</p>", "visibility": "public"},
    }
    mock_session = MockClientSession([])

    result = await _process_mention(
        mock_session, "https://example.social", "token123",
        notification, {}
    )
    assert result is None  # Empty prompt should return None
