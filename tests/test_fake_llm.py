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


def test_embed_dimension_and_determinism():
    a = embeddings.embed("hello world")
    b = embeddings.embed("hello world")
    c = embeddings.embed("otro texto distinto")
    assert len(a) == cfg.embed_dim
    assert a == b
    assert a != c
