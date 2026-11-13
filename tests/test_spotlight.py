import asyncio
import random
from datetime import date, timedelta

import pytest

from app import spotlight
from app.scheduler import weekly_spotlight


def test_theme_rotates_every_week():
    themes = {spotlight.theme_for(date(2026, 1, 5) + timedelta(weeks=w)) for w in range(len(spotlight.THEMES))}
    assert themes == set(spotlight.THEMES)


@pytest.mark.parametrize("text, ok", [
    ("¿Te has preguntado hasta dónde puedes llegar? ✈️", True),
    ("Hay 200 oportunidades esperándote", False),        # cifra
    ("Este mensaje automático te trae novedades", False),
    ("Plazas limitadas, ¡corre!", False),
    ("Mira www.algo.com", False),
    ("", False),
    ("a" * 200, False),
])
def test_hook_validation(text, ok):
    assert (spotlight.validate_line(text, 150) is None) is ok


def test_formats_escape_html_and_convert_markup():
    text = "**A & B** <script> [ver](https://x.eu/1)"
    assert spotlight.to_telegram_html(text) == '<b>A &amp; B</b> &lt;script&gt; <a href="https://x.eu/1">ver</a>'
    assert spotlight.to_whatsapp(text) == "*A & B* <script> ver: https://x.eu/1"


def test_whatsapp_bold_link_and_bare_url():
    assert spotlight.to_whatsapp("• **[Eco](https://m.eu/1)**") == "• *Eco*: https://m.eu/1"
    assert spotlight.to_whatsapp("[m.eu](https://m.eu)") == "https://m.eu"


def test_number_and_km_format():
    assert spotlight._num(6.7) == "6,7" and spotlight._num(7.0) == "7"
    assert spotlight._km(4043) == "4.043"


def test_hook_falls_back_without_llm():
    hook, closing = asyncio.run(spotlight.write_hook("destino", "x", random.Random(1)))
    assert hook in spotlight.FALLBACK_HOOKS["destino"]
    assert closing in spotlight.FALLBACK_CLOSINGS
    for hooks in spotlight.FALLBACK_HOOKS.values():
        assert all(spotlight.validate_line(h, 150) is None for h in hooks)


def test_build_skips_themes_without_data(monkeypatch):
    seen = []

    async def body_for(name, _today, _rng):
        seen.append(name)
        return ("cuerpo", "ctx") if name == "erasmus" else None

    monkeypatch.setattr(spotlight, "body_for", body_for)
    result = asyncio.run(weekly_spotlight.build(date(2026, 11, 18), theme="records", rng=random.Random(1)))
    assert result[0] == "erasmus" and "cuerpo" in result[1]
    assert seen == ["records", "destino", "erasmus"]


def test_place_and_country_names():
    assert spotlight._place({"location": "Pignola, Italy", "country_code": "IT"}) == "Pignola, Italia"
    assert spotlight._place({"location": "Yerevan, AM", "country_code": "AM"}) == "Yerevan, Armenia"
    assert spotlight._country("NL") == "Países Bajos"


def test_tidy_and_gendered_words():
    assert spotlight._tidy("¡Compártelo! ✨!") == "¡Compártelo! ✨"
    assert spotlight.validate_line("¿Lista para despegar?", 150) is not None


@pytest.mark.parametrize("text", [
    "¿Cansada de lo de siempre?", "Viaja sin gastarte apenas nada", "Algo que te cambiará la vida",
    "Sin dinero de por medio",
])
def test_hook_rejects_gender_and_claims(text):
    assert spotlight.validate_line(text, 150) is not None


def test_non_eu_countries_in_spanish():
    assert spotlight._place({"location": "Cairo, Egypt", "country_code": "EG"}) == "Cairo, Egipto"
    assert spotlight._country("MK") == "Macedonia del Norte"


@pytest.mark.parametrize("text", ["¿Estás preparade?", "Una oportunidad única", "¡Comparte y spread the love!"])
def test_hook_rejects_odd_wording(text):
    assert spotlight.validate_line(text, 150) is not None
