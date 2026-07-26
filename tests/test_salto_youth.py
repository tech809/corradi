"""Tests offline (sin red) con HTML sintético que reproduce la estructura real vista en
salto-youth.net (2026-07-25/26) — ver `app/sources/salto_youth.py`.

Sin pytest-asyncio en el proyecto (no se usa en ningún otro test): cada test es una
función síncrona normal que envuelve su cuerpo async con `asyncio.run()`."""
import asyncio

import httpx

from app.sources import salto_youth as salto

DISCLAIMER_HTML = """
<div class="tool-item-disclaimer"><h6><strong>Disclaimer!</strong></h6>
<p>Information about training activities reaches SALTO from the most
different directions. SALTO cannot be held responsible for incorrect information or changes
in the training activities. However, please inform SALTO, whenever you should come upon
incorrect data in the European Training Calender. Always contact the organisers of the
training activities themselves for the latest information.</p>
</div>
"""

# Bug real: en algunas fichas el disclaimer sale ANTES del bloque "Apply now!"/fecha
# límite (no después, como se asumió al principio) — cortar el cuerpo en su posición se
# comía la fecha límite real. Este fixture reproduce justo ese orden.
DETAIL_HTML = f"""
<html><body>
<div>You are here: Start / Reset &amp; Recharge</div>
<div>All new training offers in your inbox: Be the first to know about new training
offers with our <a href="#">e-mail notifications</a>.</div>
<h1>Reset &amp; Recharge</h1>
<p>Training Course</p>
<p>10-19 August 2026 | Pamporovo, Bulgaria</p>
<p>A training course for youth workers focused on well-being.</p>
<p>More information can be found in the <strong>INFOPACK</strong>:
<a href="https://drive.google.com/file/d/abc123/view">Link</a></p>
{DISCLAIMER_HTML}
<a href="/tools/european-training-calendar/application-procedure/16541/"
   class="fx-dialog button round-button callforaction">Apply now!</a>
<p>Application deadline (24h UTC): 30 July 2026</p>
<p>This Training Course is for 18 participants from Bulgaria, Cyprus, Greece, Italy, Spain
and recommended for Youth workers, Trainers</p>
</body></html>
"""

APPLY_EXTERNAL_HTML = """
<html><body>
<p>Applications for this training activity are handled on an external website and not on
SALTO-YOUTH.net!</p>
<p>(Notice: You will be forwarded to https://forms.gle/yzBxCFogBwkxGc8G9.)</p>
</body></html>
"""

APPLY_INTERNAL_HTML = "<html><body><p>Fill in the form below.</p></body></html>"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_probe_id_public():
    def handler(request):
        if str(request.url).startswith("http://trainings.salto-youth.net/"):
            return httpx.Response(
                302, headers={"location": "https://www.salto-youth.net/tools/european-training-calendar/training/reset-recharge.15120/"}
            )
        return httpx.Response(200, text=DETAIL_HTML)

    async def go():
        async with _client(handler) as client:
            return await salto.probe_id(client, 15120)

    result = asyncio.run(go())
    assert result["status"] == "public"
    assert result["url"].endswith("reset-recharge.15120/")
    assert "Reset &amp; Recharge" in result["html"]  # html en bruto, sin desescapar todavía


def test_probe_id_draft_when_redirected_to_login():
    def handler(request):
        if str(request.url).startswith("http://trainings.salto-youth.net/"):
            return httpx.Response(
                302, headers={"location": "https://www.salto-youth.net/mysalto/login/?pfad=%2Ftools%2F..."}
            )
        return httpx.Response(200, text="<html>login</html>")

    async def go():
        async with _client(handler) as client:
            return await salto.probe_id(client, 15128)

    assert asyncio.run(go())["status"] == "draft"


def test_probe_id_missing_on_404():
    def handler(request):
        return httpx.Response(404)

    async def go():
        async with _client(handler) as client:
            return await salto.probe_id(client, 99999)

    assert asyncio.run(go())["status"] == "missing"


def test_quick_relevance_check_training_course_spain_eligible():
    assert salto.quick_relevance_check(DETAIL_HTML) is True


def test_quick_relevance_check_wrong_type():
    html = "<p>This Study Visit is for 10 participants from Spain and recommended for youth workers</p>"
    assert salto.quick_relevance_check(html) is False


def test_quick_relevance_check_country_not_eligible():
    html = "<p>This Training Course is for 10 participants from Austria, Slovak Republic and recommended for youth workers</p>"
    assert salto.quick_relevance_check(html) is False


def test_quick_relevance_check_unknown_format_returns_none():
    """Sin la frase reconocible, no se descarta a ciegas — se deja pasar (None = no
    determinado), mejor gastar una llamada de más que perder algo bueno."""
    assert salto.quick_relevance_check("<p>Página con una forma totalmente distinta</p>") is None


def test_build_opportunity_text_strips_nav_and_appends_links():
    def handler(request):
        return httpx.Response(200, text=APPLY_EXTERNAL_HTML)

    async def go():
        async with _client(handler) as client:
            return await salto.build_opportunity_text(client, DETAIL_HTML, "https://www.salto-youth.net/.../reset-recharge.15120/")

    text = asyncio.run(go())
    assert text is not None
    assert "You are here" not in text  # nav recortada
    assert "Disclaimer" not in text
    assert "SALTO cannot be held responsible" not in text  # el párrafo entero, no solo el título
    assert "Reset & Recharge" in text
    assert "Training Course" in text
    # Bug real: el disclaimer sale ANTES del bloque de fecha límite en muchas fichas —
    # si se recortara ahí en vez de solo quitar el párrafo, esto se perdería.
    assert "Application deadline (24h UTC): 30 July 2026" in text
    assert "Infopack: https://drive.google.com/file/d/abc123/view" in text
    assert "Enlace de inscripción: https://forms.gle/yzBxCFogBwkxGc8G9" in text  # resuelto, no la página intermedia


def test_resolve_application_url_falls_back_to_salto_page_when_internal():
    def handler(request):
        return httpx.Response(200, text=APPLY_INTERNAL_HTML)

    async def go():
        async with _client(handler) as client:
            return await salto._resolve_application_url(client, "https://www.salto-youth.net/.../application-procedure/1/")

    url = asyncio.run(go())
    assert url == "https://www.salto-youth.net/.../application-procedure/1/"


def test_build_opportunity_text_returns_none_on_unexpected_page():
    async def go():
        async with _client(lambda r: httpx.Response(200)) as client:
            return await salto.build_opportunity_text(
                client, "<html><body>Página completamente distinta</body></html>", "https://www.salto-youth.net/.../weird.1/"
            )

    assert asyncio.run(go()) is None
