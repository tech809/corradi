import io

from PIL import Image

from app.publisher import card_v2

BASE = {"identifier": "CORRADI-2026-0001", "title": "Green Roots on the Air", "country_code": "IT"}


def _open(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def test_render_devuelve_png_1200x350_por_cada_tipo():
    for t in ("YOUTH_EXCHANGE", "TRAINING_COURSE", "VOLUNTEERING"):
        img = _open(card_v2.render({**BASE, "type": t}))
        assert img.format == "PNG"
        assert img.size == (1200, 350)


def test_render_no_lanza_con_titulo_larguisimo_ni_sin_pais():
    opp = {
        "identifier": "CORRADI-2026-0002", "type": "TRAINING_COURSE", "country_code": None,
        "title": "A " + "very " * 40 + "long title that will never fit in two lines no matter what",
    }
    assert _open(card_v2.render(opp)).size == (1200, 350)


def test_fetch_photo_cae_al_pool_sin_image_url():
    b = card_v2._fetch_photo({**BASE, "type": "YOUTH_EXCHANGE"})
    assert b and _open(b).size[0] > 0  # es una imagen válida del pool


def test_fetch_photo_media_local_inexistente_no_lanza_y_usa_pool():
    b = card_v2._fetch_photo({**BASE, "image_url": "/media/opportunities/" + "f" * 32 + ".jpg"})
    assert b is not None  # cae al pool en vez de romper


def test_pool_photo_es_determinista_por_identificador():
    a = card_v2.pool_photo("CORRADI-2026-0123")
    b = card_v2.pool_photo("CORRADI-2026-0123")
    assert a == b and a is not None


def test_invalid_remote_photo_falls_back_to_pool(monkeypatch):
    import httpx
    from types import SimpleNamespace
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: SimpleNamespace(
        content=b"<html>not an image</html>", raise_for_status=lambda: None,
    ))
    assert card_v2._fetch_photo({**BASE, "image_url": "https://example.org/broken.jpg"}) == card_v2.pool_photo(BASE["identifier"])


def test_flags_preserve_original_proportions_and_details():
    from app.publisher.opportunity_card import _flag, FLAG_DIR
    for code in ("GR", "ES", "PT", "CY", "CZ", "CH", "HR", "SK", "SI"):
        with Image.open(FLAG_DIR / (code.lower() + ".png")) as source:
            from PIL import ImageOps
            expected = ImageOps.contain(source.convert("RGBA"), (120, 80), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (140, 100), "#999999")
        _flag(canvas, 10, 10, 120, 80, code.lower())
        left = 10 + (120 - expected.width) // 2
        top = 10 + (80 - expected.height) // 2
        assert canvas.crop((left, top, left + expected.width, top + expected.height)).tobytes() == expected.convert("RGB").tobytes()
