from io import BytesIO

from PIL import Image

from app.publisher import instagram_card


OPPORTUNITY = {
    "title": "Digital Detox in the Mountains",
    "type": "YOUTH_EXCHANGE",
    "country_code": "PL",
    "location": "Piotrków Trybunalski, Poland",
    "start_date": "2026-06-23",
    "end_date": "2026-06-30",
    "topic": "bienestar digital, naturaleza y participación juvenil",
}


def test_feed_uses_project_photo_and_keeps_instagram_dimensions(monkeypatch):
    monkeypatch.setattr(
        instagram_card, "_project_photo",
        lambda _opp, size: Image.new("RGB", size, "#c43228"),
    )
    rendered = instagram_card.render_feed(OPPORTUNITY, "23 de junio")
    with Image.open(BytesIO(rendered)) as image:
        assert image.size == instagram_card.FEED_SIZE
        # Centro alto: debe seguir siendo la foto, no el antiguo fondo de categoría.
        red, green, blue = image.convert("RGB").getpixel((540, 260))
        assert red > green * 2 and red > blue * 2


def test_story_falls_back_without_photo(monkeypatch):
    monkeypatch.setattr(instagram_card, "_project_photo", lambda _opp, _size: None)
    rendered = instagram_card.render_story(OPPORTUNITY, "quedan 3 días")
    with Image.open(BytesIO(rendered)) as image:
        assert image.size == instagram_card.STORY_SIZE
        assert image.format == "PNG"
