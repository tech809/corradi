from io import BytesIO

from PIL import Image

from app.publisher import instagram, reel_video


def test_reel_frames_reuse_story_design(monkeypatch):
    story = BytesIO()
    Image.new("RGB", reel_video.SIZE, "#2a78d6").save(story, "PNG")
    monkeypatch.setattr(reel_video, "render_story", lambda _opp, _label: story.getvalue())

    first = next(reel_video._render_frames({"title": "Project"}))

    assert len(first) == reel_video.SIZE[0] * reel_video.SIZE[1] * 3


def test_hook_uses_destination_and_has_safe_fallback():
    assert reel_video._hook_copy({"location": "Braga, Portugal"}) == "¿TE IRÍAS A BRAGA?"
    assert "ERASMUS+" in reel_video._hook_copy({})


def test_reel_has_distinct_hook_information_and_cta_scenes(monkeypatch):
    story = BytesIO()
    Image.new("RGB", reel_video.SIZE, "#2a78d6").save(story, "PNG")
    monkeypatch.setattr(reel_video, "render_story", lambda _opp, _label: story.getvalue())
    bg, hook, cta = reel_video._build_reel_assets({"title": "Project", "location": "Braga"})

    hook_frame = reel_video._compose_frame(bg, hook, cta, 0.7).convert("RGB")
    info_frame = reel_video._compose_frame(bg, hook, cta, 3.0).convert("RGB")
    cta_frame = reel_video._compose_frame(bg, hook, cta, 7.0).convert("RGB")

    # El centro está velado en el hook, vuelve a la tarjeta en información y termina con
    # el panel claro del CTA: no son ya 8 segundos de una misma tarjeta casi estática.
    assert hook_frame.getpixel((540, 900)) != info_frame.getpixel((540, 900))
    assert cta_frame.getpixel((540, 900)) != info_frame.getpixel((540, 900))


def test_reel_duration_covers_all_three_acts():
    assert 0 < reel_video.HOOK_END < reel_video.COVER_TIME < reel_video.CTA_START < reel_video.DURATION


def test_reel_caption_invites_comments_and_saves_without_changing_feed_caption():
    opp = {"title": "Project", "location": "Braga, Portugal"}

    assert "Etiquétale en comentarios" in instagram.build_reel_caption(opp)
    assert "Guárdalo" in instagram.build_reel_caption(opp)
    assert "Etiquétale" not in instagram.build_caption(opp)
