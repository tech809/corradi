import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from app import instagram_auth
from app.publisher import instagram
from app.scheduler import publish_instagram


def _mock_sweep_lock(monkeypatch, granted=True):
    class Cursor:
        async def fetchone(self):
            return (granted,)

    class Connection:
        async def execute(self, _sql):
            return Cursor()

    @asynccontextmanager
    async def connection():
        yield Connection()

    monkeypatch.setattr(publish_instagram, "get_pool", lambda: SimpleNamespace(connection=connection))


def test_meta_code_190_is_a_distinct_auth_failure():
    response = httpx.Response(
        400, json={"error": {"code": 190, "message": "Session has expired"}},
        request=httpx.Request("GET", "https://graph.instagram.com/me"),
    )
    with pytest.raises(instagram.InstagramTokenExpired, match="190"):
        instagram._raise_for_graph_error(response)


def test_expired_token_leaves_queue_untouched_and_notifies(monkeypatch):
    calls = []

    async def record(name):
        calls.append(name)

    async def expired():
        raise instagram.InstagramTokenExpired("expired")

    monkeypatch.setattr(publish_instagram.instagram, "is_configured", lambda: True)
    monkeypatch.setattr(publish_instagram.instagram, "check_token", expired)
    monkeypatch.setattr(publish_instagram, "open_pool", lambda: record("open"))
    monkeypatch.setattr(publish_instagram, "close_pool", lambda: record("close"))
    monkeypatch.setattr(publish_instagram.instagram_auth, "notify_expired", lambda: record("alert"))
    monkeypatch.setattr(publish_instagram.repo, "list_pending_instagram", lambda *_: record("queue"))
    _mock_sweep_lock(monkeypatch)

    asyncio.run(publish_instagram.run())
    assert calls == ["open", "alert", "close"]


def test_expiry_notice_is_addressed_to_pachu(monkeypatch):
    sent = []

    async def claim(_fingerprint):
        return True

    async def alert(_subject, _detail, recipient_ids):
        sent.append(recipient_ids)

    monkeypatch.setattr(instagram_auth.repo, "claim_instagram_auth_alert", claim)
    monkeypatch.setattr(instagram_auth.alerts, "alert", alert)
    monkeypatch.setattr(instagram_auth, "cfg", SimpleNamespace(
        instagram_alert_telegram_id=4120346, instagram_token="test-token",
    ))
    asyncio.run(instagram_auth.notify_expired())
    assert sent == [[4120346]]


def test_story_recovery_does_not_repeat_feed(monkeypatch):
    calls = []

    async def noop(*_args):
        return None

    async def empty(*_args):
        return []

    async def stories(*_args):
        return [{"queue_id": 8, "identifier": "CORRADI-2026-0577", "attempts": 1}]

    async def story(_row):
        calls.append("story")
        return "story-media-id"

    async def saved(_queue_id, _story_id):
        calls.append("saved")

    async def feed(_row):
        calls.append("feed")

    monkeypatch.setattr(publish_instagram.instagram, "is_configured", lambda: True)
    monkeypatch.setattr(publish_instagram.instagram, "check_token", noop)
    monkeypatch.setattr(publish_instagram.instagram, "publish_story", story)
    monkeypatch.setattr(publish_instagram.instagram, "publish_opportunity", feed)
    monkeypatch.setattr(publish_instagram.repo, "list_pending_instagram", empty)
    monkeypatch.setattr(publish_instagram.repo, "list_missing_instagram_stories", stories)
    monkeypatch.setattr(publish_instagram.repo, "mark_instagram_story_published", saved)
    monkeypatch.setattr(publish_instagram, "open_pool", noop)
    monkeypatch.setattr(publish_instagram, "close_pool", noop)
    _mock_sweep_lock(monkeypatch)

    asyncio.run(publish_instagram.run())
    assert calls == ["story", "saved"]


def test_second_sweep_exits_when_first_holds_lock(monkeypatch):
    calls = []

    async def record(name):
        calls.append(name)

    monkeypatch.setattr(publish_instagram.instagram, "is_configured", lambda: True)
    monkeypatch.setattr(publish_instagram.instagram, "check_token", lambda: record("check"))
    monkeypatch.setattr(publish_instagram, "open_pool", lambda: record("open"))
    monkeypatch.setattr(publish_instagram, "close_pool", lambda: record("close"))
    _mock_sweep_lock(monkeypatch, granted=False)

    asyncio.run(publish_instagram.run())
    assert calls == ["open", "close"]
