import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app import instagram_auth
from app.publisher import instagram
from app.scheduler import publish_instagram


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
