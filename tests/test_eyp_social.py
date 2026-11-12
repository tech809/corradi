import asyncio
import random
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.scheduler import publish_esc_social, scrape_eyp
from app import pipeline


def test_scrape_eyp_only_ingests_and_never_publishes(monkeypatch):
    rows = [{"id": 1}, {"id": 2}]
    published = []

    async def fetch_open(_client, _today):
        return rows

    async def upsert(fields):
        return {"id": fields["source_external_id"]}, fields["source_external_id"] == 1

    async def noop(*_args, **_kwargs):
        return None

    async def zero(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(scrape_eyp.eyp, "fetch_open", fetch_open)
    monkeypatch.setattr(scrape_eyp.eyp, "select_candidates", lambda data, *_args: data)
    monkeypatch.setattr(
        scrape_eyp.eyp, "to_project", lambda item, _checked: {"source_external_id": item["id"]},
    )
    monkeypatch.setattr(scrape_eyp.repo, "upsert_eyp_project", upsert)
    monkeypatch.setattr(scrape_eyp.repo, "close_missing_eyp_projects", zero)
    monkeypatch.setattr(pipeline, "publish_existing_eyp", lambda p: published.append(p))
    monkeypatch.setattr(scrape_eyp, "open_pool", noop)
    monkeypatch.setattr(scrape_eyp, "close_pool", noop)

    result = asyncio.run(scrape_eyp.run())

    assert published == []
    assert result["created"] == 1
    assert result["updated"] == 1


@pytest.mark.parametrize("hour, minute, low, high", [
    (17, 0, 0, 3 * 3600), (18, 30, 0, 1.5 * 3600), (20, 0, 0, 0), (21, 15, 0, 0), (9, 0, 8 * 3600, 11 * 3600),
])
def test_random_slot_falls_between_17_and_20(hour, minute, low, high):
    now = datetime(2026, 11, 12, hour, minute, tzinfo=ZoneInfo("Europe/Madrid"))
    for seed in range(50):
        delay = publish_esc_social.seconds_until_random_slot(now, random.Random(seed))
        assert low <= delay <= high
        if delay:
            assert 17 <= (now + timedelta(seconds=delay)).hour < 20


@pytest.mark.parametrize("candidates, expected", [
    ([], None),
    ([
        {"identifier": "POBRE", "application_deadline": date(2026, 11, 20)},
        {"identifier": "COMPLETA", "application_deadline": date(2026, 12, 1),
         "summary": "x", "detailed_description": "x"},
    ], "COMPLETA"),
])
def test_esc_social_publishes_best_recent_candidate(monkeypatch, candidates, expected):
    published = []

    async def list_candidates(_since, _today):
        return candidates

    async def publish(project):
        published.append(project["identifier"])
        return {"published": True}

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(publish_esc_social.repo, "list_eyp_social_candidates", list_candidates)
    monkeypatch.setattr(publish_esc_social.pipeline, "publish_existing_eyp", publish)
    monkeypatch.setattr(publish_esc_social, "open_pool", noop)
    monkeypatch.setattr(publish_esc_social, "close_pool", noop)
    monkeypatch.setattr(publish_esc_social, "cfg", SimpleNamespace(
        eyp_social_daily_cap=1, timezone="Europe/Madrid",
    ))

    result = asyncio.run(publish_esc_social.run(wait=False))

    assert published == ([expected] if expected else [])
    assert result["published"] is bool(expected)
def test_social_eyp_guarda_foto_editorial_antes_de_publicar(monkeypatch):
    project = {"id": "project-id", "identifier": "CORRADI-2026-0612", "image_url": None}
    saved = []
    rendered = []

    def enrich(row):
        return {**row, "image_url": "https://images.pexels.com/photo.jpg", "image_origin": "pexels"}

    async def update(_identifier, fields):
        saved.append(fields)
        return {**project, **fields}

    async def publish(_image, _caption, **_kwargs):
        return 123

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline.images, "enrich", enrich)
    monkeypatch.setattr(pipeline.repo, "update_project", update)
    monkeypatch.setattr(pipeline.repo, "mark_published", noop)
    monkeypatch.setattr(pipeline.repo, "mark_eyp_social_published", noop)
    monkeypatch.setattr(pipeline.pub, "format_opportunity", lambda *_args, **_kwargs: "caption")
    monkeypatch.setattr(pipeline.pub, "opportunity_keyboard", lambda *_args: None)
    monkeypatch.setattr(pipeline.pub, "publish_photo_to_channel", publish)
    monkeypatch.setattr(pipeline.card_v2, "render", lambda row: rendered.append(row) or b"photo")
    monkeypatch.setattr(pipeline.handoff, "opportunity", noop)
    monkeypatch.setattr(pipeline, "_publish_instagram_background", noop)

    result = asyncio.run(pipeline.publish_existing_eyp(project))

    assert result["published"] is True
    assert saved[0]["image_url"] == "https://images.pexels.com/photo.jpg"
    assert rendered[0]["image_url"] == saved[0]["image_url"]
