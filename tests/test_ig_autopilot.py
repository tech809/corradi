import asyncio
import io
import random
import wave
from datetime import date

import pytest
from PIL import Image

from app.ig_auto import content as C
from app.ig_auto import design as D
from app.ig_auto import learn, music
from app.ig_auto.autopilot import CALENDAR
from app.publisher import instagram

TODAY = date(2026, 11, 13)
OPP = {"id": "p1", "identifier": "CORRADI-2026-0001", "title": "HOST, WELCOME, RECEIVE – Rethinking Hospitality",
       "type": "TRAINING_COURSE", "country_code": "FR", "location": "Dordoña, Francia",
       "start_date": date(2026, 12, 1), "end_date": date(2026, 12, 7), "application_deadline": date(2026, 11, 25),
       "summary": "Formación sobre cómo acoger a voluntarios internacionales en Dordoña.", "max_participants": 20,
       "eligibility_country_codes": ["ES", "FR"], "eligibility_scope": "explicit", "image_url": None}


def test_hook_only_uses_structured_data():
    h = C.hook(OPP, "afirmacion")
    assert h["lines"] == ["7 días", "en Francia."] and h["hl"] == ["Francia"]
    assert C.hook(OPP, "pregunta")["lines"] == ["¿Te vas", "7 días a", "Francia?"]
    long = {**OPP, "end_date": date(2027, 11, 30)}
    assert C.hook(long, "afirmacion")["lines"][0] == "12 meses"
    assert C.hook({**OPP, "start_date": None}, "pregunta")["lines"] == ["Erasmus+", "en Francia."]
    assert "cubierto" not in " ".join(h["lines"]).lower()


def test_stats_and_dates():
    assert C.stats(OPP) == [("7", "días"), ("20", "plazas"), ("25 nov", "plazo")]
    assert C.dates(OPP) == "1–7 dic"
    assert C.country("NL") == "Países Bajos" and C.country("EG") == "Egipto"


def test_summary_falls_back_when_english():
    eng = {**OPP, "summary": "We are an NGO and the volunteers work with the community.", "topic": "inclusión"}
    assert C.summary(eng) == "Temas: inclusión."


def test_pick_featured_filters_and_varies_country():
    rows = [OPP, {**OPP, "id": "p2", "country_code": "IT", "location": "Roma"},
            {**OPP, "id": "p3", "application_deadline": date(2026, 11, 15)},          # cierra pronto
            {**OPP, "id": "p4", "eligibility_country_codes": ["FR"]}]                  # sin España
    pick = C.pick_featured(rows, TODAY, set(), ["FR"], {})
    assert pick["id"] == "p2"
    assert C.pick_featured(rows, TODAY, {"p1", "p2"}, [], {}) is None


def test_lastcall_items_only_ye_tc_within_week():
    rows = [{**OPP, "application_deadline": date(2026, 11, 15)},
            {**OPP, "type": "VOLUNTEERING", "application_deadline": date(2026, 11, 15)},
            {**OPP, "application_deadline": date(2026, 12, 1)}]
    items = C.lastcall_items(rows, TODAY)
    assert len(items) == 1 and items[0]["closes"] == "15 nov"


def test_guides_have_no_unchecked_claims():
    for g in C.GUIDES:
        text = " ".join([*g["lines"], g["sub"], *(t + s for t, s in g["cards"]), g["close_sub"], g["caption"]]).lower()
        assert "gratis" not in text and "garantiz" not in text


def test_learning_explores_then_exploits():
    hist = []
    v = learn.choose("carousel_opp", hist, random.Random(1))
    assert v["hook"] in learn.DIMENSIONS["carousel_opp"]["hook"] and v["hour"] in (13, 19, 21)
    for hook, sc in (("afirmacion", 0.1), ("afirmacion", 0.1), ("pregunta", 0.5), ("pregunta", 0.5)):
        hist.append({"kind": "carousel_opp", "score": sc, "variant": {"hook": hook, "hour": 19}})
    picks = [learn.choose("carousel_opp", hist, random.Random(i))["hook"] for i in range(200)]
    assert picks.count("pregunta") > 140
    assert learn.score({"reach": 100, "saved": 5, "shares": 2, "likes": 10, "comments": 1}) > \
        learn.score({"reach": 100, "saved": 0, "shares": 0, "likes": 10, "comments": 0})


def test_calendar_covers_every_day():
    assert set(CALENDAR) == set(range(7))
    assert all(k in learn.DIMENSIONS for kinds in CALENDAR.values() for k in kinds)


@pytest.mark.parametrize("style", sorted(music.STYLES))
def test_music_styles_render(style):
    raw = music.render(style, 3, seed=3)
    w = wave.open(io.BytesIO(raw))
    assert w.getnchannels() == 2 and abs(w.getnframes() / w.getframerate() - 3) < 0.01


def _size(jpeg):
    return Image.open(io.BytesIO(jpeg)).size


def test_design_pieces_render():
    hook = C.hook(OPP, "pregunta")
    assert _size(D.cover(None, hook, OPP["type"])) == D.FEED
    assert _size(D.details(OPP, C.stats(OPP), C.summary(OPP))) == D.FEED
    assert _size(D.apply_slide("25 nov", C.apply_steps(OPP), "Guárdalo")) == D.FEED
    assert _size(D.story(None, hook, OPP["type"], "PLAZO 25 NOV")) == D.STORY
    items = C.lastcall_items([{**OPP, "application_deadline": date(2026, 11, 15)}] * 6, TODAY)
    assert _size(D.lastcall_cover(len(items), ["FR"], "ink")) == D.FEED
    assert _size(D.lastcall_list(items[:5], "2/2")) == D.FEED
    for g in C.GUIDES:
        for bg in D.BACKGROUNDS:
            assert _size(D.guide_cover(g["kicker"], g["lines"], g["hl"], g["sub"], bg)) == D.FEED
        assert _size(D.guide_cards(g["heading"], g["cards"], g["footnote"], "2/3")) == D.FEED
        assert _size(D.guide_closing(g["close_kicker"], g["close_lines"], g["close_hl"], g["close_sub"], "x", "3/3")) == D.FEED


def test_new_opportunities_go_to_stories_only(monkeypatch):
    calls = []

    async def story(opp):
        calls.append("story")
        return "S1"

    async def create(*_a, **_k):
        calls.append("feed")
        return "F1"

    monkeypatch.delenv("IG_FEED_PER_OPPORTUNITY", raising=False)
    monkeypatch.setattr(instagram, "is_configured", lambda: True)
    monkeypatch.setattr(instagram, "publish_story", story)
    monkeypatch.setattr(instagram, "_create_and_publish", create)
    assert asyncio.run(instagram.publish_opportunity(OPP)) == ("S1", "S1")
    assert calls == ["story"]
