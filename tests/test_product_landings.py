from pathlib import Path
from datetime import date

import pytest

from app.api import landing
from app.api.main import _short_link_page


STATIC = Path(__file__).parents[1] / "app" / "api" / "static"


def test_country_type_landing_has_specific_metadata_and_filters():
    body = landing.build(STATIC, "italia", "training-course")
    assert "Training Courses en Italia · Corradi" in body
    assert '"country": "IT"' in body
    assert '"type": "TRAINING_COURSE"' in body
    assert 'rel="canonical" href="https://mapa.proactivefuture.eu/oportunidades/italia/training-course"' in body


def test_country_landing_without_type_is_supported():
    body = landing.build(STATIC, "portugal")
    assert "oportunidades Erasmus+ en Portugal" in body
    assert '"country": "PT"' in body
    assert '"type": null' in body


def test_unknown_landing_returns_404():
    with pytest.raises(KeyError):
        landing.build(STATIC, "atlantida")


def test_short_link_keeps_specific_whatsapp_preview_and_opens_map():
    body = _short_link_page({
        "identifier": "CORRADI-2026-1020", "title": "Jóvenes & Europa",
        "type": "YOUTH_EXCHANGE", "location": "Lisboa", "status": "open",
        "application_deadline": date(2026, 12, 1),
    }, "https://mapa.proactivefuture.eu")
    assert 'property="og:title" content="Jóvenes &amp; Europa"' in body
    assert 'property="og:url" content="https://mapa.proactivefuture.eu/2026-1020"' in body
    assert 'location.replace("/mapa?o=CORRADI-2026-1020")' in body
    assert 'href="/mapa?o=CORRADI-2026-1020"' in body
    assert "opportunityMap" not in body
