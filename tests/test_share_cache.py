"""GET /share/{id}/story.png: caché en disco, ETag/304, formato y tamaño."""
import asyncio
import dataclasses
import io
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import main, share_cache
from app.db import repository as repo
from app.publisher import instagram_card

URL = "/share/CORRADI-2026-0001/story.png"


def _row(**extra):
    row = {
        "identifier": "CORRADI-2026-0001", "title": "Jóvenes & Europa", "type": "YOUTH_EXCHANGE",
        "country_code": "IT", "location": "Roma", "status": "open",
        "application_deadline": date.today() + timedelta(days=10),
        "start_date": date.today() + timedelta(days=40), "end_date": date.today() + timedelta(days=47),
        "updated": datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc), "image_url": None,
    }
    row.update(extra)
    return row


@pytest.fixture
def state(tmp_path, monkeypatch):
    """Fila mutable + contador de renders; el render de verdad se sustituye por uno barato."""
    st = {"row": _row(), "renders": 0}

    async def get(identifier):
        return st["row"] if identifier == st["row"]["identifier"] else None

    def fake_render(opp, label, image_format="PNG", jpeg_quality=85):
        st["renders"] += 1
        return f"{image_format}|{opp['title']}|{label}".encode()

    monkeypatch.setattr(repo, "get_by_identifier", get)
    monkeypatch.setattr(instagram_card, "render_share", fake_render)
    monkeypatch.setattr(main, "_share_cache", share_cache.ShareImageCache(tmp_path, 50, 10, 24))
    st["dir"] = tmp_path
    return st


@pytest.fixture
def client():
    return TestClient(main.app)


def test_cache_hit_avoids_rerender(client, state):
    first = client.get(URL)
    second = client.get(URL)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert state["renders"] == 1
    assert len(list(state["dir"].glob("*.jpg"))) == 1


def test_project_update_changes_key_and_rerenders(client, state):
    first = client.get(URL)
    state["row"] = _row(title="Título nuevo", updated=datetime(2026, 11, 2, tzinfo=timezone.utc))
    second = client.get(URL)
    assert state["renders"] == 2
    assert first.headers["etag"] != second.headers["etag"]
    assert b"T\xc3\xadtulo nuevo" in second.content


def test_updated_timestamp_alone_changes_key():
    a = share_cache.cache_key(_row(), "quedan 10 días", "jpeg", 85)
    b = share_cache.cache_key(_row(updated=datetime(2026, 11, 5, tzinfo=timezone.utc)), "quedan 10 días", "jpeg", 85)
    assert a != b


def test_relative_deadline_label_is_part_of_key():
    """"quedan N días" cambia cada día: otra etiqueta, otra imagen."""
    a = share_cache.cache_key(_row(), "quedan 10 días", "jpeg", 85)
    b = share_cache.cache_key(_row(), "quedan 9 días", "jpeg", 85)
    assert a != b
    # Campos que la tarjeta no pinta (p. ej. contadores) no invalidan.
    assert a == share_cache.cache_key(_row(clicks=42), "quedan 10 días", "jpeg", 85)


def test_etag_and_304(client, state):
    first = client.get(URL)
    etag = first.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')
    again = client.get(URL, headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag
    assert client.get(URL, headers={"If-None-Match": f'"x", W/{etag}'}).status_code == 304
    assert client.get(URL, headers={"If-None-Match": '"otro"'}).status_code == 200
    assert state["renders"] == 1


def test_missing_project_404(client, state):
    assert client.get("/share/CORRADI-2099-9999/story.png").status_code == 404


def test_concurrent_requests_render_once(tmp_path):
    cache = share_cache.ShareImageCache(tmp_path, 50, 10, 24)
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return b"img"

    async def run():
        return await asyncio.gather(*(cache.get_or_render("k", "jpeg", render) for _ in range(8)))

    assert asyncio.run(run()) == [b"img"] * 8
    assert calls["n"] == 1
    assert not cache._locks and not cache._inflight


def test_concurrent_requests_render_once_without_disk(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    cache = share_cache.ShareImageCache(blocker / "sub", 50, 10, 24)  # no se puede crear
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return b"img"

    async def run():
        return await asyncio.gather(*(cache.get_or_render("k", "jpeg", render) for _ in range(5)))

    assert asyncio.run(run()) == [b"img"] * 5
    assert calls["n"] == 1


def test_eviction_bounds_files_and_bytes(tmp_path):
    cache = share_cache.ShareImageCache(tmp_path, 3, 10, 24)

    async def fill():
        for i in range(6):
            await cache.get_or_render(f"k{i}", "jpeg", lambda i=i: asyncio.sleep(0, b"x" * 10))

    asyncio.run(fill())
    assert len(list(tmp_path.glob("*.jpg"))) == 3

    small = share_cache.ShareImageCache(tmp_path / "mb", 100, 1, 24)  # 1 MB
    async def fill_big():
        for i in range(4):
            await small.get_or_render(f"b{i}", "jpeg", lambda: asyncio.sleep(0, b"x" * 400_000))

    asyncio.run(fill_big())
    assert sum(p.stat().st_size for p in (tmp_path / "mb").glob("*.jpg")) <= 1024 * 1024


def test_expired_entry_is_rerendered(tmp_path):
    import os
    cache = share_cache.ShareImageCache(tmp_path, 50, 10, 1)
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return b"img"

    asyncio.run(cache.get_or_render("k", "jpeg", render))
    path = next(tmp_path.glob("*.jpg"))
    old = path.stat().st_mtime - 2 * 3600
    os.utime(path, (old, old))
    asyncio.run(cache.get_or_render("k", "jpeg", render))
    assert calls["n"] == 2


@pytest.mark.parametrize("fmt,ctype,pil", [("jpeg", "image/jpeg", "JPEG"), ("png", "image/png", "PNG")])
def test_real_render_content_type_matches_bytes(client, tmp_path, monkeypatch, fmt, ctype, pil):
    async def get(identifier):
        return _row()

    monkeypatch.setattr(repo, "get_by_identifier", get)
    monkeypatch.setattr(main, "cfg", dataclasses.replace(main.cfg, share_image_format=fmt))
    monkeypatch.setattr(main, "_share_cache", share_cache.ShareImageCache(tmp_path, 50, 10, 24))
    response = client.get(URL)
    assert response.status_code == 200
    assert response.headers["content-type"] == ctype
    with Image.open(io.BytesIO(response.content)) as img:
        assert img.format == pil
        assert img.size == instagram_card.STORY_SIZE
    if fmt == "jpeg":
        assert len(response.content) <= 300 * 1024
        assert 'filename="corradi-CORRADI-2026-0001.jpg"' in response.headers["content-disposition"]
