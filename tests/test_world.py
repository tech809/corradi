from pathlib import Path
import asyncio

from app.scheduler import scrape_salto_world
from app.publisher.world_telegram import format_opportunity
from app.sources import salto_world


def _salto_html(activity="Training Course", countries="Spain, Romania, Greece"):
    return (
        f"<p>This {activity} is for 24 participants from {countries} "
        "and recommended for Youth workers</p>"
    )


def test_world_salto_accepts_training_courses_from_any_country():
    html = _salto_html(countries="Austria, Slovak Republic")
    assert salto_world.quick_relevance_check(html) is True
    assert salto_world.parse_eligibility(html)[:2] == (["AT", "SK"], "explicit")


def test_world_salto_still_rejects_other_activity_types():
    assert salto_world.quick_relevance_check(_salto_html("Study Visit")) is False


def test_world_salto_expands_broad_programme_eligibility():
    codes, scope, label = salto_world.parse_eligibility(
        _salto_html(countries="Erasmus+ Youth Programme countries")
    )
    assert scope == "all_programme"
    assert {"ES", "RO", "GR", "TR", "NO"}.issubset(codes)
    assert label == "Erasmus+ Youth Programme countries"


def test_world_salto_detects_closed_calls_before_using_the_llm():
    assert salto_world.is_clearly_closed("<h2>Applications are closed</h2>") is True
    assert salto_world.is_clearly_closed("<p>Apply now!</p>") is False


def test_world_frontend_is_english_and_uses_its_own_api():
    page = (Path(__file__).parents[1] / "app" / "api" / "static" / "world.html").read_text()
    assert '<html lang="en">' in page
    assert "Where do you currently live?" in page
    assert "fetch('/world/api/opportunities')" in page
    assert "fetch('/api/map')" not in page


def test_world_scraper_saves_to_world_catalog_without_spanish_pipeline(monkeypatch):
    html = _salto_html(countries="Romania, Greece") + "<p>Apply now!</p>"
    saved = {}

    async def probe(_client, _id):
        return {"status": "public", "url": "https://salto.example/15000", "html": html}

    async def build(_client, _html, _url):
        return "Training Course in Bucharest. Application deadline: 20 December 2026."

    def extract(_text, _today):
        return {
            "is_opportunity": True, "type": "TRAINING_COURSE", "title": "Test course",
            "raw_message": "source", "country_code": "RO", "location": "Bucharest, Romania",
            "deadline_in_past": False,
        }

    async def upsert(fields, source_id, source_url, codes, scope):
        saved.update(fields=fields, source_id=source_id, source_url=source_url, codes=codes, scope=scope)
        return {"identifier": "WORLD-2026-0001"}

    statuses = []
    monkeypatch.setattr(scrape_salto_world.salto, "probe_id", probe)
    monkeypatch.setattr(scrape_salto_world.salto, "build_opportunity_text", build)
    monkeypatch.setattr(scrape_salto_world.extractor, "extract_world", extract)
    monkeypatch.setattr(scrape_salto_world.extractor, "flush_usage", lambda: _async_none())
    monkeypatch.setattr(scrape_salto_world.geo, "geocode", lambda *_args: (44.43, 26.10))
    monkeypatch.setattr(scrape_salto_world.world_repo, "upsert_salto_project", upsert)

    async def status(id_num, value, identifier=None):
        statuses.append((id_num, value, identifier))

    monkeypatch.setattr(scrape_salto_world.world_repo, "upsert_salto_id", status)

    result = asyncio.run(scrape_salto_world._process_id(object(), 15000))
    assert result == "saved"
    assert saved["codes"] == ["GR", "RO"]
    assert saved["fields"]["latitude"] == 44.43
    assert statuses[-1] == (15000, "saved", "WORLD-2026-0001")
    assert "from app import pipeline" not in Path(scrape_salto_world.__file__).read_text()


def test_world_usage_accounting_never_blocks_ingestion(monkeypatch):
    async def broken_flush():
        raise RuntimeError("metrics table unavailable")

    monkeypatch.setattr(scrape_salto_world.extractor, "flush_usage", broken_flush)
    asyncio.run(scrape_salto_world._flush_usage_safely())


async def _async_none():
    return None


def test_world_telegram_copy_is_english_and_includes_eligibility():
    text = format_opportunity({
        "title": "Facilitation Lab", "country_code": "RO", "location": "Bucharest, Romania",
        "application_deadline": "2026-12-20", "eligibility_countries": "Spain, Greece, Romania",
        "summary": "A practical course for youth workers.",
    })
    assert "Eligible residents" in text
    assert "Apply by" in text
    assert "Fecha" not in text
