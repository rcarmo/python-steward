"""Tests for ACP server integration."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from acp import text_block

from steward.acp import StewardAcpAgent


class FakeClient:
    def __init__(self) -> None:
        self.updates: List[Dict[str, Any]] = []

    async def session_update(self, session_id: str, update, **kwargs: Any) -> None:  # noqa: ANN001
        self.updates.append({"session_id": session_id, "update": update})


@pytest.mark.asyncio
async def test_acp_prompt_sends_update(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = StewardAcpAgent()
    client = FakeClient()
    agent.on_connect(client)

    session = await agent.new_session(cwd="/tmp", mcp_servers=[])

    def _fake_run(options):  # noqa: ANN001
        return type("Result", (), {"response": "ok", "messages": [], "last_response_id": None})()

    monkeypatch.setattr("steward.acp.run_steward_with_history", _fake_run)

    response = await agent.prompt(prompt=[text_block("hello")], session_id=session.session_id)
    assert response.stop_reason == "end_turn"
    assert client.updates
    assert client.updates[0]["session_id"] == session.session_id


@pytest.mark.asyncio
async def test_acp_load_session_creates_state() -> None:
    agent = StewardAcpAgent()
    await agent.load_session(cwd="/tmp", mcp_servers=[], session_id="abc")
    assert "abc" in agent._sessions
