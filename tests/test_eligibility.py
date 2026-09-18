from datetime import date

from app.domain.project import normalize
from app.eligibility import PROGRAMME_COUNTRY_CODES, parse_eligibility_label


def test_spanish_explicit_countries_are_structured():
    codes, scope = parse_eligibility_label("Participantes residentes en España, Italia y Rumanía")
    assert codes == ["ES", "IT", "RO"]
    assert scope == "explicit"


def test_programme_country_group_is_expanded():
    codes, scope = parse_eligibility_label("Países del programa Erasmus+")
    assert set(codes) == set(PROGRAMME_COUNTRY_CODES)
    assert scope == "all_programme"


def test_unknown_eligibility_stays_unknown_instead_of_guessing():
    assert parse_eligibility_label("Consultar requisitos con la organización") == ([], "unknown")


def test_normalize_adds_structured_eligibility():
    result = normalize(
        {"eligibility_countries": "España, Grecia", "application_deadline": "30/09/2026"},
        date(2026, 9, 18),
        7,
    )
    assert result["eligibility_country_codes"] == ["ES", "GR"]
    assert result["eligibility_scope"] == "explicit"
