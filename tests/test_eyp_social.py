import asyncio
from datetime import date

from app.scheduler import scrape_eyp


def test_only_new_eyp_rows_fill_remaining_daily_social_slots(monkeypatch):
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    projects = {
        1: {"id": "p1", "identifier": "EYP-1", "application_deadline": date(2026, 10, 1),
            "summary": "x", "detailed_description": "x", "participant_profile": "x"},
        2: {"id": "p2", "identifier": "EYP-2", "application_deadline": date(2026, 10, 2)},
        3: {"id": "p3", "identifier": "EYP-3", "application_deadline": date(2026, 10, 3)},
    }
    published = []

    async def fetch_open(_client, _today):
        return rows

    async def upsert(fields):
        return projects[fields["source_external_id"]], True

    async def publish(project):
        published.append(project["identifier"])
        return {"published": True}

    async def noop(*_args, **_kwargs):
        return None

    async def close_missing(*_args, **_kwargs):
        return 0

    async def already_published(*_args, **_kwargs):
        return 1  # con tope 2 solo queda una plaza hoy

    monkeypatch.setattr(scrape_eyp.eyp, "fetch_open", fetch_open)
    monkeypatch.setattr(scrape_eyp.eyp, "select_candidates", lambda data, *_args: data)
    monkeypatch.setattr(
        scrape_eyp.eyp, "to_project",
        lambda item, _checked: {"source_external_id": item["id"]},
    )
    monkeypatch.setattr(scrape_eyp.repo, "upsert_eyp_project", upsert)
    monkeypatch.setattr(scrape_eyp.repo, "close_missing_eyp_projects", close_missing)
    monkeypatch.setattr(scrape_eyp.repo, "count_eyp_social_published_on", already_published)
    monkeypatch.setattr(scrape_eyp.pipeline, "publish_existing_eyp", publish)
    monkeypatch.setattr(scrape_eyp, "open_pool", noop)
    monkeypatch.setattr(scrape_eyp, "close_pool", noop)

    result = asyncio.run(scrape_eyp.run())

    assert published == ["EYP-1"]
    assert result["created"] == 3
    assert result["social_published"] == 1


def test_updated_eyp_rows_never_drain_into_social_backlog(monkeypatch):
    rows = [{"id": 1}]
    published = []

    async def fetch_open(_client, _today):
        return rows

    async def upsert(_fields):
        return {"id": "old", "identifier": "EYP-OLD"}, False

    async def noop(*_args, **_kwargs):
        return None

    async def zero(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(scrape_eyp.eyp, "fetch_open", fetch_open)
    monkeypatch.setattr(scrape_eyp.eyp, "select_candidates", lambda data, *_args: data)
    monkeypatch.setattr(scrape_eyp.eyp, "to_project", lambda item, _checked: item)
    monkeypatch.setattr(scrape_eyp.repo, "upsert_eyp_project", upsert)
    monkeypatch.setattr(scrape_eyp.repo, "close_missing_eyp_projects", noop)
    monkeypatch.setattr(scrape_eyp.repo, "count_eyp_social_published_on", zero)
    monkeypatch.setattr(
        scrape_eyp.pipeline, "publish_existing_eyp",
        lambda project: published.append(project),
    )
    monkeypatch.setattr(scrape_eyp, "open_pool", noop)
    monkeypatch.setattr(scrape_eyp, "close_pool", noop)

    result = asyncio.run(scrape_eyp.run())

    assert published == []
    assert result["updated"] == 1
    assert result["social_published"] == 0
