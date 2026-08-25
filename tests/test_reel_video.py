from io import BytesIO

from PIL import Image

from app.publisher import reel_video


def test_reel_frames_reuse_story_design(monkeypatch):
    story = BytesIO()
    Image.new("RGB", reel_video.SIZE, "#2a78d6").save(story, "PNG")
    monkeypatch.setattr(reel_video, "render_story", lambda _opp, _label: story.getvalue())

    first = next(reel_video._render_frames({"title": "Project"}))

    assert len(first) == reel_video.SIZE[0] * reel_video.SIZE[1] * 3
