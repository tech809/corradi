"""Mejoras técnicas de la API pública: /api/stats, /api/map, last_minute, /proyecto, sitemap."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.db import repository as repo


def _row(identifier="CORRADI-2026-0001", **extra):
    row = {
        "identifier": identifier, "title": "Jóvenes & Europa", "type": "YOUTH_EXCHANGE",
        "country_code": "IT", "location": "Roma", "summary": "Intercambio sobre clima.",
        "status": "open", "application_deadline": date.today() + timedelta(days=10),
        "raw_message": "LAST MINUTE! Quedan 2 plazas", "submitted_by": "Ana (@ana)",
        "submitted_by_id": 123, "telegram_message_id": 99, "max_participants": 30,
        "publication_scope": "web", "duration_days": 7,
    }
    row.update(extra)
    return row


@pytest.fixture
def client():
    # Sin `with`: no se ejecuta el lifespan (no abre el pool de la BD).
    return TestClient(main.app)


def test_serialize_adds_last_minute_without_leaking_raw_message():
    out = main._serialize(_row())
    assert out["last_minute"] is True
    assert "raw_message" not in out and "submitted_by" not in out and "submitted_by_id" not in out
    assert main._serialize(_row(raw_message="Convocatoria normal"))["last_minute"] is False
    assert main._serialize(_row(raw_message=None))["last_minute"] is False


def test_opportunity_detail_exposes_last_minute(client, monkeypatch):
    async def get(identifier):
        return _row(identifier)
    monkeypatch.setattr(repo, "get_by_identifier", get)
    body = client.get("/opportunities/CORRADI-2026-0001").json()
    assert body["last_minute"] is True
    assert "raw_message" not in body
    assert body["max_participants"] == 30  # el detalle conserva todos los campos públicos


def test_api_map_omits_unused_fields_but_keeps_used_ones(client, monkeypatch):
    async def list_open():
        return [_row()]
    monkeypatch.setattr(repo, "list_open", list_open)
    item = client.get("/api/map").json()["results"][0]
    for field in main._MAP_OMIT_FIELDS:
        assert field not in item
    for field in ("identifier", "title", "detailed_description", "eligibility_country_codes",
                  "channel_url", "approx_location", "last_minute", "updated"):
        assert field in item
    assert "raw_message" not in item


def test_api_stats_drops_closed_and_is_cached(client, monkeypatch):
    calls = {"n": 0}

    async def count_total_published():
        calls["n"] += 1
        return 5

    async def zero(*_a, **_k):
        return 0

    async def empty(*_a, **_k):
        return []

    async def no_clicks():
        return {}

    async def interest(days=30):
        return {"period_days": days, "by_type": [], "by_country": [], "top_projects": []}

    async def boom(*_a, **_k):
        raise AssertionError("list_closed ya no debe llamarse")

    monkeypatch.setattr(main, "_stats_cache", None)
    monkeypatch.setattr(repo, "count_total_published", count_total_published)
    monkeypatch.setattr(repo, "count_open", zero)
    monkeypatch.setattr(repo, "get_total_visits", zero)
    for name in ("country_breakdown_all", "monthly_counts", "organiser_breakdown",
                 "daily_visits_since", "heatmap_points", "contributors_breakdown"):
        monkeypatch.setattr(repo, name, empty)
    monkeypatch.setattr(repo, "get_click_counts", no_clicks)
    monkeypatch.setattr(repo, "interest_breakdown", interest)
    monkeypatch.setattr(repo, "list_closed", boom)

    first = client.get("/api/stats").json()
    second = client.get("/api/stats").json()
    assert "closed" not in first
    assert first == second and first["total_published"] == 5
    assert calls["n"] == 1  # la segunda sale de la caché en proceso


def test_project_page_404_for_missing_and_200_for_closed(client, monkeypatch):
    rows = {"CORRADI-2025-0001": _row("CORRADI-2025-0001", status="closed",
                                      application_deadline=date(2025, 1, 1))}

    async def get(identifier):
        return rows.get(identifier)
    monkeypatch.setattr(repo, "get_by_identifier", get)

    missing = client.get("/proyecto/CORRADI-2099-9999")
    assert missing.status_code == 404
    assert "noindex" in missing.text and "text/html" in missing.headers["content-type"]

    closed = client.get("/proyecto/CORRADI-2025-0001")
    assert closed.status_code == 200
    assert 'content="noindex,follow"' in closed.text


def test_project_page_injects_seo_metadata(client, monkeypatch):
    async def get(identifier):
        return _row(identifier, image_url="/media/opportunities/" + "a" * 32 + ".jpg")
    monkeypatch.setattr(repo, "get_by_identifier", get)
    monkeypatch.setattr(main, "_public_origin", lambda: "https://mapa.example")
    response = client.get("/proyecto/CORRADI-2026-0001")
    body = response.text
    assert response.status_code == 200
    assert body.count("<title>") == 1
    assert "<title>Jóvenes &amp; Europa · Corradi Erasmus+</title>" in body
    assert body.count('<meta name="description"') == 1
    assert '<meta name="description" content="Youth Exchange en Roma. Intercambio sobre clima.">' in body
    assert '<link rel="canonical" href="https://mapa.example/proyecto/CORRADI-2026-0001">' in body
    assert '<meta property="og:title" content="Jóvenes &amp; Europa · Corradi Erasmus+">' in body
    assert 'property="og:image" content="https://mapa.example/media/opportunities/' in body
    assert "index,follow" in body
    # Revalidación barata con el ETag del contenido ya inyectado.
    again = client.get("/proyecto/CORRADI-2026-0001", headers={"If-None-Match": response.headers["etag"]})
    assert again.status_code == 304


def test_sitemap_lists_pages_and_canonical_project_urls(client, monkeypatch):
    async def list_open():
        return [_row("CORRADI-2026-0001"),
                _row("CORRADI-2026-0002", application_deadline=date.today() - timedelta(days=1))]
    monkeypatch.setattr(repo, "list_open", list_open)
    monkeypatch.setattr(main, "_public_origin", lambda: "https://mapa.example")
    xml = client.get("/sitemap.xml").text
    for path in ("/", "/mapa", "/guia", "/organizaciones", "/quienes-somos", "/estadisticas"):
        assert f"<loc>https://mapa.example{path}</loc>" in xml
    assert "<loc>https://mapa.example/proyecto/CORRADI-2026-0001</loc>" in xml
    assert "CORRADI-2026-0002" not in xml  # plazo vencido: fuera
    assert "<loc>https://mapa.example/2026-0001</loc>" not in xml  # nada de enlaces cortos


def test_internal_html_not_served_under_assets(client):
    assert client.get("/assets/publicar.html").status_code == 404
    assert client.get("/assets/PROJECT.HTML").status_code == 404
    assert client.get("/assets/logo.svg").status_code == 200


def test_mapa_trailing_slash_redirects(client):
    response = client.get("/mapa/?o=CORRADI-2026-0001", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/mapa?o=CORRADI-2026-0001"
