from datetime import date
from decimal import Decimal

from app.domain.project import make_hash, normalize, parse_date, parse_decimal, parse_int


def test_parse_date_formats():
    assert parse_date("12/09/2026") == date(2026, 9, 12)
    assert parse_date("2026-09-12") == date(2026, 9, 12)
    assert parse_date(None) is None
    assert parse_date("no es fecha") is None


def test_parse_int():
    assert parse_int("30") == 30
    assert parse_int(None) is None
    assert parse_int("null") is None


def test_parse_decimal():
    assert parse_decimal("25") == Decimal("25")
    assert parse_decimal("25,50") == Decimal("25.50")
    assert parse_decimal("€30") == Decimal("30")
    assert parse_decimal(None) is None


def test_make_hash_deterministic_and_sensitive():
    h1 = make_hash("Título", "ES", date(2026, 9, 12))
    h2 = make_hash("Título", "ES", date(2026, 9, 12))
    assert h1 == h2
    assert make_hash("Título", "ES", date(2026, 9, 13)) != h1


def test_normalize_deadline_fallback():
    f = normalize({"start_date": "12/09/2026", "application_deadline": None, "country": "es"}, date(2026, 1, 1), 7)
    assert f["deadline_estimated"] is True
    assert f["application_deadline"] == date(2026, 1, 8)
    assert f["country_code"] == "ES"
    assert f["start_date"] == date(2026, 9, 12)


def test_normalize_deadline_explicit():
    f = normalize({"application_deadline": "25/08/2026"}, date(2026, 1, 1), 7)
    assert f["deadline_estimated"] is False
    assert f["application_deadline"] == date(2026, 8, 25)
