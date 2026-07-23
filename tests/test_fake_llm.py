from app.config import cfg
from app.llm import embeddings, extractor


def test_extract_opportunity():
    f = extractor.extract(
        'YOUTH EXCHANGE "X"\nSpain, Oviedo\nDates: 12/09/2026 - 20/09/2026\n'
        "Apply before 25/08/2026: https://forms.gle/x"
    )
    assert f["is_opportunity"] is True
    assert f["country_code"] == "ES"
    assert f["start_date"].isoformat() == "2026-09-12"
    assert f["end_date"].isoformat() == "2026-09-20"
    assert f["application_deadline"].isoformat() == "2026-08-25"
    assert f["deadline_estimated"] is False
    assert f["application_url"].startswith("http")
    assert f["type"] == "YOUTH_EXCHANGE"


def test_extract_non_opportunity():
    f = extractor.extract("Hola a todos, gracias por el finde!")
    assert f["is_opportunity"] is False
    assert f.get("reason")


def test_extract_with_corrections_applies_and_keeps_raw_clean():
    """Las correcciones (flujo Modificar/Editar) ajustan la extracción, pero raw_message
    se guarda limpio para que no afecte a la deduplicación."""
    from datetime import date
    ref = date(2026, 7, 23)
    base = extractor.extract("YOUTH EXCHANGE en Italia\nInicio 12/09/2026\nhttps://forms.gle/x", ref)
    assert base["end_date"] is None

    corr = extractor.extract(
        "YOUTH EXCHANGE en Italia\nInicio 12/09/2026\nhttps://forms.gle/x", ref,
        corrections=["la fecha de fin es 20/09/2026"],
    )
    assert corr["end_date"].isoformat() == "2026-09-20"
    # La corrección NO entra en el texto guardado:
    assert "fin es" not in corr["raw_message"]
    assert corr["raw_message"] == base["raw_message"]


def test_embed_dimension_and_determinism():
    a = embeddings.embed("hello world")
    b = embeddings.embed("hello world")
    c = embeddings.embed("otro texto distinto")
    assert len(a) == cfg.embed_dim
    assert a == b
    assert a != c
