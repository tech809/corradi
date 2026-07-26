from datetime import date
from decimal import Decimal

from app.domain.project import (
    is_last_minute, is_online_only, make_hash, normalize, parse_date, parse_decimal, parse_int,
)


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
    f = normalize({"start_date": "12/09/2026", "application_deadline": None, "country": "es"}, date(2026, 1, 1), 5)
    assert f["deadline_estimated"] is True
    assert f["application_deadline"] == date(2026, 1, 6)
    assert f["country_code"] == "ES"
    assert f["start_date"] == date(2026, 9, 12)


def test_normalize_deadline_explicit():
    f = normalize({"application_deadline": "25/08/2026"}, date(2026, 1, 1), 5)
    assert f["deadline_estimated"] is False
    assert f["application_deadline"] == date(2026, 8, 25)
    assert f["deadline_in_past"] is False


def test_is_last_minute():
    assert is_last_minute("¡ÚLTIMA HORA! Quedan plazas para Italia")
    assert is_last_minute("ultimas plazas disponibles")
    assert is_last_minute("Last minute opportunity in Poland")
    assert not is_last_minute("Intercambio juvenil en Grecia, plazas abiertas")
    assert not is_last_minute(None)


def test_normalize_last_minute_shortens_estimated_deadline():
    f = normalize(
        {"application_deadline": None}, date(2026, 7, 22), 5,
        raw_text="🚨 ÚLTIMA HORA: quedan 2 plazas para el intercambio en Italia",
        last_minute_deadline_days=2,
    )
    assert f["last_minute"] is True
    assert f["deadline_estimated"] is True
    assert f["application_deadline"] == date(2026, 7, 24)  # +2 días, no +5


def test_normalize_flags_past_deadline():
    """Una fecha límite explícita ya vencida NO se empuja al año siguiente: se marca para
    que el pipeline rechace la oportunidad por estar fuera de plazo."""
    f = normalize({"application_deadline": "10/07/2026"}, date(2026, 7, 22), 5)
    assert f["deadline_in_past"] is True
    assert f["stated_deadline"] == date(2026, 7, 10)


def test_normalize_deadline_today_is_not_past():
    f = normalize({"application_deadline": "22/07/2026"}, date(2026, 7, 22), 5)
    assert f["deadline_in_past"] is False


def test_normalize_flags_deadline_too_far():
    """Deadline explícita a más de 3 meses vista: red de seguridad ante un año mal inferido
    (p.ej. el caso real que la disparó: '17/07' sin año, procesado el 22/07 -> el LLM la
    empujó a 2027 en vez de sospechar del propio dato)."""
    f = normalize({"application_deadline": "17/07/2027"}, date(2026, 7, 22), 5, max_deadline_months=3)
    assert f["deadline_too_far"] is True


def test_normalize_deadline_within_3_months_is_fine():
    f = normalize({"application_deadline": "15/09/2026"}, date(2026, 7, 22), 5, max_deadline_months=3)
    assert f["deadline_too_far"] is False


def test_normalize_deadline_too_far_respects_custom_months():
    f = normalize({"application_deadline": "15/12/2026"}, date(2026, 7, 22), 5, max_deadline_months=6)
    assert f["deadline_too_far"] is False


def test_is_online_only_detects_common_hints():
    """Bug real: 'ID Talks: Social Sport' (location='Online (Zoom)') se coló publicada."""
    assert is_online_only("Online (Zoom)") is True
    assert is_online_only("Virtual") is True
    assert is_online_only("Webinar") is True
    assert is_online_only("Remoto") is True


def test_is_online_only_false_for_physical_location():
    assert is_online_only("Oviedo, España") is False
    assert is_online_only("Jastrzębia Góra, Poland") is False


def test_is_online_only_false_for_missing_location():
    """Sin ubicación no es lo mismo que online — es un dato que falta, no una señal
    positiva de que sea online. No se debe rechazar por esto."""
    assert is_online_only(None) is False
    assert is_online_only("") is False


def test_is_online_only_word_boundary_no_false_positive():
    """'Skopje' no debe disparar por contener una subcadena parecida a ninguna pista."""
    assert is_online_only("Skopje, North Macedonia") is False


def test_normalize_flags_online_location():
    f = normalize({"location": "Online (Zoom)"}, date(2026, 7, 22), 5)
    assert f["is_online"] is True


def test_normalize_does_not_flag_physical_location():
    f = normalize({"location": "Vilnius, Lithuania"}, date(2026, 7, 22), 5)
    assert f["is_online"] is False
