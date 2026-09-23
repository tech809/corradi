from datetime import date, datetime, timezone

from app.sources import european_youth_portal as eyp


def row(**overrides):
    base = {
        "id": 123, "title": "Nature team", "status": "open", "is_esc_related": True,
        "funding_programme": {"is_volunteering": True, "is_humanitarian": False},
        "volunteer_countries": ["ES", "FR"], "country": "IT", "town": "Torino",
        "date_start": "2026-11-01T12:00:00", "date_end": "2026-12-01T12:00:00",
        "date_application_end": "2026-10-01T12:00:00", "topics": ["natr"],
        "description": "  Restore   a forest. ", "organisation_name": "Green Org",
        "geocode": {"lat": "45.0", "lon": "7.0"},
    }
    base.update(overrides)
    return base


def test_select_candidates_is_strict_about_deadline_spain_and_future_start():
    now = datetime(2026, 9, 23, 7, tzinfo=timezone.utc)
    rows = [
        row(id=1),
        row(id=2, date_application_end=None, has_no_deadline=True),
        row(id=3, volunteer_countries=["FR"]),
        row(id=4, date_start="2026-09-01T12:00:00"),
        row(id=5, date_application_end="2027-01-01T12:00:00"),
    ]
    assert [item["id"] for item in eyp.select_candidates(rows, now, date(2026, 12, 23))] == [1]


def test_to_project_is_web_only_and_keeps_official_trace():
    project = eyp.to_project(row(), datetime(2026, 9, 23, 7, tzinfo=timezone.utc))
    assert project["type"] == "VOLUNTEERING"
    assert project["publication_scope"] == "web"
    assert project["source"] == "eyp"
    assert project["source_external_id"] == "123"
    assert project["application_url"].endswith("/123_en")
    assert project["application_deadline"] == date(2026, 10, 1)
    assert project["summary"] == "Restore a forest."
    assert project["duration_days"] == 31
    assert project["duration_months"] == 1.0
    assert project["eligibility_country_codes"] == ["ES", "FR"]
    assert project["latitude"] == 45.0


def test_to_project_converts_portal_html_and_entities_to_readable_text():
    project = eyp.to_project(
        row(
            description=(
                "<p>💸 Volunteer with us – Costs Covered!</p>"
                "<ul><li>Flights &amp; daily commute ✈️</li><li>Private bedroom 🛏️</li></ul>"
            ),
            participant_profile="<p>Curious &amp; motivated<br>Age 18–30</p>",
        ),
        datetime(2026, 9, 23, 7, tzinfo=timezone.utc),
    )
    assert project["detailed_description"] == (
        "💸 Volunteer with us – Costs Covered!\n"
        "• Flights & daily commute ✈️\n"
        "• Private bedroom 🛏️"
    )
    assert project["participant_profile"] == "Curious & motivated\nAge 18–30"
    assert "<p>" not in project["summary"]
    assert "&amp;" not in project["summary"]

    inline_list = eyp.to_project(
        row(description="<p>Costs covered: - Private bedroom - Food &amp; travel - Pocket money</p>"),
        datetime(2026, 9, 23, 7, tzinfo=timezone.utc),
    )
    assert inline_list["detailed_description"] == (
        "Costs covered:\n• Private bedroom\n• Food & travel\n• Pocket money"
    )
