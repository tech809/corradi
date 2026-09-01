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
