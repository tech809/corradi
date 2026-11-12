import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app import pipeline
from app.db import repository as repo


@pytest.mark.parametrize("used, reserved, sends", [(0, 1, 1), (1, 1, 0), (2, 1, 0), (0, 0, 0)])
def test_reservation_commits_before_send(monkeypatch, used, reserved, sends):
    events = []

    class Connection:
        async def execute(self, sql, params):
            events.append(sql)
            async def fetchone():
                return (used,)
            return SimpleNamespace(fetchone=fetchone, rowcount=reserved)

    @asynccontextmanager
    async def connection():
        yield Connection()
        events.append("commit")

    async def send():
        events.append("send")
        return 42

    monkeypatch.setattr(repo, "get_pool", lambda: SimpleNamespace(connection=connection))
    monkeypatch.setattr(repo, "cfg", SimpleNamespace(timezone="Europe/Madrid", eyp_social_daily_cap=9))
    result = asyncio.run(repo.publish_esc_with_daily_cap("project", send))
    assert events.count("send") == sends
    assert result == (42 if sends else None)
    assert "pg_advisory_xact_lock" in events[0]
    assert "type='VOLUNTEERING'" in events[1]
    assert "source='eyp'" in events[1]
    if sends:
        assert events.index("commit") < events.index("send")


def test_portal_esc_uses_daily_quota(monkeypatch):
    calls = []

    async def capped(project_id, send):
        calls.append(project_id)
        return None

    monkeypatch.setattr(pipeline.repo, "publish_esc_with_daily_cap", capped)
    result = asyncio.run(pipeline._publish_telegram_opportunity({
        "id": "esc", "type": "VOLUNTEERING", "source": "eyp",
    }))
    assert result is None
    assert calls == ["esc"]


@pytest.mark.parametrize("source", ["gestor", "telegram", "whatsapp"])
def test_bot_esc_skips_quota_like_ye_or_tc(monkeypatch, source):
    async def capped(*_args):
        raise AssertionError("un ESC del bot no debe pasar por el cupo")

    async def publish(_image, _caption, **_kwargs):
        return 77

    monkeypatch.setattr(pipeline.repo, "publish_esc_with_daily_cap", capped)
    monkeypatch.setattr(pipeline.pub, "format_opportunity", lambda *_a, **_k: "caption")
    monkeypatch.setattr(pipeline.pub, "opportunity_keyboard", lambda *_a: None)
    monkeypatch.setattr(pipeline.pub, "publish_photo_to_channel", publish)
    monkeypatch.setattr(pipeline.card_v2, "render", lambda _row: b"photo")
    result = asyncio.run(pipeline._publish_telegram_opportunity({
        "id": "esc", "type": "VOLUNTEERING", "source": source,
    }))
    assert result == 77
