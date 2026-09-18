from pathlib import Path

import pytest

from app.api import landing


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
