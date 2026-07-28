"""Descubre oportunidades de SALTO-YOUTH escaneando IDs secuenciales de fichas
(`trainings.salto-youth.net/<id>`) para `app/scheduler/scrape_salto.py`.

NUNCA se usa el listado paginado/ordenado (`.../browse/?b_offset=...`): el `robots.txt` de
salto-youth.net prohíbe explícitamente `b_offset`, `b_order` y `b_limit` (investigado
2026-07-25). El atajo `trainings.salto-youth.net/<id>` no lleva ninguno de esos tres
parámetros, así que no cae bajo esa prohibición — y como los IDs son correlativos con el
alta de cada ficha, escanear hacia arriba desde el último conocido detecta lo nuevo al
momento, incluso con fecha límite lejana (punto ciego real del enfoque anterior por
listado, que ordenaba por fecha límite y podía tardar semanas en mostrar algo nuevo).

Cada ID probado puede salir:
- "missing" (404): el ID aún no existe.
- "draft": existe pero redirige a login — ficha aún no pública, se reintenta más adelante.
- "public": ficha real, con su HTML.

Cada ficha pública da un texto en bruto listo para `app.llm.extractor.extract()`, igual
que si un coordinador lo hubiera escrito a mano — el "cerebro" de extracción es el mismo
para cualquier fuente, esto solo hace de "boca" nueva (mismo patrón que Telegram/WhatsApp).
"""
from __future__ import annotations

import html as html_lib
import re

import httpx

_UA = "Mozilla/5.0 (compatible; CorradiBot/1.0; +https://proactivefuture.eu)"
_BASE = "https://www.salto-youth.net"
_TRAININGS_HOST = "trainings.salto-youth.net"

_APPLY_HREF_RE = re.compile(r'href="([^"]+)"[^>]*class="[^"]*callforaction[^"]*"')
_INFOPACK_RE = re.compile(r'INFOPACK.{0,120}?href="([^"]+)"', re.S)
# Patrón real observado en producción (2026-07-29, ficha Art-Mind): el enlace de descarga
# del PDF va en un <a class="download-helper ... wfd-filetype-pdf">, sin la palabra
# "INFOPACK" cerca -- el regex de arriba nunca matcheaba ahi, asi que el href se perdia
# y el LLM se quedaba solo con el TEXTO visible del enlace (el nombre del fichero, p.ej.
# "Art-Mind, INFO PACK.pdf") como si fuera la URL -- infopack_url quedaba con un nombre
# de fichero en vez de un enlace real. Se prueban los dos patrones, el que primero
# matchee gana.
_INFOPACK_DOWNLOAD_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*class="[^"]*download-helper[^"]*"', re.S)
_FORWARDED_RE = re.compile(r"forwarded to (https?://\S+?)\.?\)")
# Párrafo fijo de disclaimer que SALTO mete en TODAS las fichas — su posición varía según
# la ficha (a veces antes del bloque "Apply now!"/fecha límite, a veces después), así que
# se ELIMINA el párrafo tal cual en vez de truncar el cuerpo en su posición (bug real
# encontrado: truncar ahí se comía la fecha límite real en la mitad de los casos).
_DISCLAIMER_RE = re.compile(r"Disclaimer!.*?for the latest information\.", re.S)

# Filtro barato (sin LLM) de tipo + país elegible, sobre la frase fija que SALTO genera en
# cada ficha ("This <tipo> is for N participants from <países> and recommended for..."):
# ahorra la llamada a Gemini en fichas claramente irrelevantes. Si no se puede determinar
# (formato inesperado), se deja pasar — mejor gastar una llamada de más que descartar algo
# bueno por un fallo de esta detección barata.
_TYPE_COUNTRY_RE = re.compile(
    r"This (.+?) is for \d+ participants from (.+?) and recommended for"
)
_ELIGIBLE_HINTS = ("spain", "erasmus+ youth programme countries")


def _strip_tags(raw_html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def quick_relevance_check(raw_html: str) -> bool | None:
    """True/False si está claro que (no) es un Training Course abierto a España; None si
    no se pudo determinar (formato inesperado) — en ese caso, procesar de todas formas."""
    flat = re.sub(r"\s+", " ", _strip_tags(raw_html))
    m = _TYPE_COUNTRY_RE.search(flat)
    if not m:
        return None
    activity_type, countries = m.group(1).lower(), m.group(2).lower()
    if "training course" not in activity_type:
        return False
    return any(hint in countries for hint in _ELIGIBLE_HINTS)


async def probe_id(client: httpx.AsyncClient, id_num: int) -> dict:
    """Sonda un ID de ficha. Devuelve {"status": "missing"} | {"status": "draft"} |
    {"status": "public", "url": ..., "html": ...} | {"status": "error"}."""
    url = f"http://{_TRAININGS_HOST}/{id_num}"
    try:
        r = await client.get(url, headers={"User-Agent": _UA}, timeout=15, follow_redirects=True)
    except httpx.HTTPError:
        return {"status": "error"}
    if r.status_code == 404:
        return {"status": "missing"}
    final_url = str(r.url)
    if "/mysalto/login/" in final_url:
        return {"status": "draft"}
    if r.status_code != 200:
        return {"status": "missing"}
    return {"status": "public", "url": final_url, "html": r.text}


async def _resolve_application_url(client: httpx.AsyncClient, apply_page_url: str) -> str:
    """El botón "Apply now!" lleva a una página intermedia de SALTO: a veces redirige a un
    formulario externo real (frase literal "Applications for this training activity are
    handled on an external website... forwarded to <url>"), a veces el formulario está en
    la propia página de SALTO — en ese caso se usa esa URL tal cual."""
    try:
        r = await client.get(apply_page_url, headers={"User-Agent": _UA}, timeout=20)
        r.raise_for_status()
        m = _FORWARDED_RE.search(r.text)
        if m:
            return html_lib.unescape(m.group(1))
    except httpx.HTTPError:
        pass
    return apply_page_url


async def build_opportunity_text(client: httpx.AsyncClient, raw_html: str, detail_url: str) -> str | None:
    """Texto en bruto de una ficha ya descargada (título, tipo, fechas, lugar, descripción
    + enlaces de infopack/inscripción añadidos como texto plano al final), listo para el
    extractor. `None` si la página no tiene la forma esperada — protección ante un cambio
    de estructura del sitio: mejor no procesar nada que procesar basura."""
    text = _strip_tags(raw_html)

    # El contenido real (título, tipo, fechas, descripción, Apply now!/fecha límite...)
    # empieza justo después de la promo de suscripción por email que precede a toda ficha.
    promo_idx = text.find("e-mail notifications")
    body = text[promo_idx + len("e-mail notifications"):] if promo_idx > 0 else text
    body = _DISCLAIMER_RE.sub("", body)
    body = body.strip(" .\n")
    if len(body) < 100:
        return None

    lines = [body]

    infopack_m = _INFOPACK_RE.search(raw_html) or _INFOPACK_DOWNLOAD_RE.search(raw_html)
    if infopack_m:
        infopack_url = html_lib.unescape(infopack_m.group(1))
        if not infopack_url.startswith("http"):
            infopack_url = _BASE + infopack_url
        lines.append(f"\nInfopack: {infopack_url}")

    apply_m = _APPLY_HREF_RE.search(raw_html)
    if apply_m:
        apply_url = html_lib.unescape(apply_m.group(1))
        if not apply_url.startswith("http"):
            apply_url = _BASE + apply_url
        ext_url = await _resolve_application_url(client, apply_url)
        lines.append(f"\nEnlace de inscripción: {ext_url}")

    lines.append(f"\nFicha original en SALTO-YOUTH: {detail_url}")
    return "\n".join(lines)
