"""Fediverse integration for steward (Mastodon API compatible servers).

Polls for mentions and executes prompts, replying with summaries.
Works with Mastodon, Pleroma, Akkoma, Misskey, and other Mastodon API compatible servers.

Configuration via environment variables:
- MASTODON_INSTANCE: Instance URL (e.g., https://mastodon.social)
- MASTODON_ACCESS_TOKEN: API access token with read:notifications, write:statuses scopes
- MASTODON_POLL_INTERVAL: Seconds between polls (default: 60)
- MASTODON_MAX_AGE_HOURS: Ignore mentions older than this (default: 24, protects against state loss)
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from os import getenv
from pathlib import Path
from typing import Optional

import aiohttp

from .runner import RunnerOptions, run_steward_with_history

REPLIED_FILE = ".steward-fediverse-replied.json"
DEFAULT_MAX_AGE_HOURS = 24


def _get_config() -> tuple[str, str, int, int]:
    """Get Mastodon configuration from environment."""
    instance = getenv("MASTODON_INSTANCE")
    token = getenv("MASTODON_ACCESS_TOKEN")
    poll_interval = int(getenv("MASTODON_POLL_INTERVAL", "60"))
    max_age_hours = int(getenv("MASTODON_MAX_AGE_HOURS", str(DEFAULT_MAX_AGE_HOURS)))

    if not instance:
        raise ValueError("MASTODON_INSTANCE environment variable required")
    if not token:
        raise ValueError("MASTODON_ACCESS_TOKEN environment variable required")

    # Normalize instance URL
    instance = instance.rstrip("/")
    if not instance.startswith("http"):
        instance = f"https://{instance}"

    return instance, token, poll_interval, max_age_hours


def _parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp from Mastodon API."""
    # Handle various ISO formats
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _is_too_old(created_at: str, max_age_hours: int) -> bool:
    """Check if a status is older than max_age_hours."""
    try:
        ts = _parse_timestamp(created_at)
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        return ts < cutoff
    except (ValueError, TypeError):
        return False  # If we can't parse, don't skip


def _load_replied() -> set[str]:
    """Load set of replied-to status IDs."""
    path = Path(REPLIED_FILE)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        return set(data.get("replied_ids", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def _save_replied(replied_ids: set[str]) -> None:
    """Save replied-to status IDs."""
    path = Path(REPLIED_FILE)
    data = {
        "replied_ids": list(replied_ids),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf8")


async def _fetch_mentions(session: aiohttp.ClientSession, instance: str, token: str) -> list[dict]:
    """Fetch recent mention notifications."""
    url = f"{instance}/api/v1/notifications"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"types[]": "mention", "limit": 30}

    async with session.get(url, headers=headers, params=params) as response:
        response.raise_for_status()
        return await response.json()


async def _get_status(session: aiohttp.ClientSession, instance: str, token: str, status_id: str) -> dict:
    """Get a single status by ID."""
    url = f"{instance}/api/v1/statuses/{status_id}"
    headers = {"Authorization": f"Bearer {token}"}

    async with session.get(url, headers=headers) as response:
        response.raise_for_status()
        return await response.json()


async def _post_reply(
    session: aiohttp.ClientSession,
    instance: str,
    token: str,
    in_reply_to_id: str,
    content: str,
    visibility: str = "unlisted",
) -> dict:
    """Post a reply status."""
    url = f"{instance}/api/v1/statuses"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "status": content,
        "in_reply_to_id": in_reply_to_id,
        "visibility": visibility,
    }

    async with session.post(url, headers=headers, data=data) as response:
        response.raise_for_status()
        return await response.json()


def _extract_prompt(content: str) -> str:
    """Extract prompt from mention content, stripping HTML and @mentions."""
    import re
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", content)
    # Remove @mentions at start
    text = re.sub(r"^(\s*@\S+\s*)+", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate_for_toot(text: str, max_chars: int = 480) -> str:
    """Truncate text to fit in a toot, leaving room for ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rsplit(" ", 1)[0] + "..."


async def _process_mention(
    session: aiohttp.ClientSession,
    instance: str,
    token: str,
    notification: dict,
    runner_options: dict,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> Optional[str]:
    """Process a single mention and return the status ID if replied."""
    status = notification.get("status", {})
    status_id = status.get("id")
    content = status.get("content", "")
    account = notification.get("account", {})
    username = account.get("acct", "unknown")
    visibility = status.get("visibility", "unlisted")

    prompt = _extract_prompt(content)
    if not prompt:
        return None

    print(f"[fediverse] Processing mention from @{username}: {prompt[:60]}...")

    # Run steward with the prompt
    try:
        options = RunnerOptions(
            prompt=prompt,
            enable_human_logs=False,
            enable_file_logs=True,
            **{k: v for k, v in runner_options.items() if v is not None}
        )
        result = run_steward_with_history(options)
        response = result.response or "(no response)"
    except Exception as exc:
        response = f"Error: {exc}"

    # Format reply
    reply = f"@{username} {_truncate_for_toot(response)}"

    # Post reply
    await _post_reply(session, instance, token, status_id, reply, visibility)
    print(f"[fediverse] Replied to @{username}")

    return status_id


async def run_fediverse_loop(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_steps: Optional[int] = None,
    system_prompt: Optional[str] = None,
    custom_instructions: Optional[str] = None,
) -> None:
    """Run the Fediverse polling loop."""
    instance, token, poll_interval, max_age_hours = _get_config()
    replied_ids = _load_replied()

    runner_options = {
        "provider": provider,
        "model": model,
        "max_steps": max_steps,
        "system_prompt": system_prompt,
        "custom_instructions": custom_instructions,
    }

    print(f"[fediverse] Starting on {instance}")
    print(f"[fediverse] Polling every {poll_interval}s, ignoring mentions older than {max_age_hours}h")
    print(f"[fediverse] {len(replied_ids)} previously replied mentions tracked")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                notifications = await _fetch_mentions(session, instance, token)

                # Filter: not already replied, and not too old
                new_mentions = []
                skipped_old = 0
                for n in notifications:
                    status = n.get("status", {})
                    status_id = status.get("id")
                    created_at = status.get("created_at", "")

                    if status_id in replied_ids:
                        continue
                    if _is_too_old(created_at, max_age_hours):
                        skipped_old += 1
                        # Mark as replied so we don't check again
                        replied_ids.add(status_id)
                        continue
                    new_mentions.append(n)

                if skipped_old > 0:
                    print(f"[fediverse] Skipped {skipped_old} old mention(s) (>{max_age_hours}h)")
                    _save_replied(replied_ids)

                if new_mentions:
                    print(f"[fediverse] Found {len(new_mentions)} new mention(s)")

                for notification in new_mentions:
                    status_id = await _process_mention(
                        session, instance, token, notification, runner_options, max_age_hours
                    )
                    if status_id:
                        replied_ids.add(status_id)
                        _save_replied(replied_ids)

            except aiohttp.ClientError as exc:
                print(f"[fediverse] API error: {exc}")
            except Exception as exc:
                print(f"[fediverse] Error: {exc}")

            await asyncio.sleep(poll_interval)


def run_fediverse(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_steps: Optional[int] = None,
    system_prompt: Optional[str] = None,
    custom_instructions: Optional[str] = None,
) -> None:
    """Run Fediverse mode (blocking)."""
    asyncio.run(run_fediverse_loop(
        provider=provider,
        model=model,
        max_steps=max_steps,
        system_prompt=system_prompt,
        custom_instructions=custom_instructions,
    ))
