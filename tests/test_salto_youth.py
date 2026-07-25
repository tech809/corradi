"""Tests offline (sin red) con HTML sintético que reproduce la estructura real vista en
salto-youth.net el 2026-07-25 — ver `app/sources/salto_youth.py`.

Sin pytest-asyncio en el proyecto (no se usa en ningún otro test): cada test es una
función síncrona normal que envuelve su cuerpo async con `asyncio.run()`."""
import asyncio
from datetime import date

import httpx

from app.sources import salto_youth as salto

LISTING_HTML = """
<html><body>
<a href="https://www.salto-youth.net/tools/european-training-calendar/training/foo-bar.15020/">Foo Bar</a>
<a href="https://www.salto-youth.net/tools/european-training-calendar/training/foo-bar.15020/">Foo Bar</a>
<a href="https://www.salto-youth.net/tools/european-training-calendar/training/baz-qux.15099/">Baz Qux</a>
</body></html>
"""

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


def test_fetch_listing_dedupes_and_preserves_order():
    def handler(request):
        return httpx.Response(200, text=LISTING_HTML)

    async def go():
        async with _client(handler) as client:
            return await salto.fetch_listing(client, date(2026, 7, 25))

    urls = asyncio.run(go())
    assert urls == [
        "https://www.salto-youth.net/tools/european-training-calendar/training/foo-bar.15020/",
        "https://www.salto-youth.net/tools/european-training-calendar/training/baz-qux.15099/",
    ]


def test_fetch_opportunity_text_strips_nav_and_appends_links():
    def handler(request):
        if "application-procedure" in str(request.url):
            return httpx.Response(200, text=APPLY_EXTERNAL_HTML)
        return httpx.Response(200, text=DETAIL_HTML)

    async def go():
        async with _client(handler) as client:
            return await salto.fetch_opportunity_text(client, "https://www.salto-youth.net/.../reset-recharge.15120/")

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


def test_fetch_opportunity_text_returns_none_on_unexpected_page():
    def handler(request):
        return httpx.Response(200, text="<html><body>Página completamente distinta</body></html>")

    async def go():
        async with _client(handler) as client:
            return await salto.fetch_opportunity_text(client, "https://www.salto-youth.net/.../weird.1/")

    assert asyncio.run(go()) is None
