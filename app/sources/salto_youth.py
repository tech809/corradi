"""Scraper conservador del European Training Calendar de SALTO-YOUTH (Training Course,
España) para `app/scheduler/scrape_salto.py`.

SOLO la página 1, en el orden y offset por defecto — NUNCA se tocan `b_offset`, `b_order`
ni `b_limit`: el `robots.txt` de salto-youth.net prohíbe explícitamente esos tres
parámetros (investigado 2026-07-25). Con ~10 resultados por página y un filtro tan
concreto (Training Course + España), es muy poco probable que entren más de 10
oportunidades nuevas en un solo día — límite conocido y aceptado por el usuario, no una
sorpresa.

Cada ficha da un texto en bruto listo para `app.llm.extractor.extract()`, igual que si un
coordinador lo hubiera escrito a mano — el "cerebro" de extracción es el mismo para
cualquier fuente, esto solo hace de "boca" nueva (mismo patrón que Telegram/WhatsApp).
"""
from __future__ import annotations

import html as html_lib
import re
from datetime import date

import httpx

_UA = "Mozilla/5.0 (compatible; CorradiBot/1.0; +https://proactivefuture.eu)"
_BASE = "https://www.salto-youth.net"
_LISTING_PATH = "/tools/european-training-calendar/browse/"

_DETAIL_RE = re.compile(
    r'href="(https://www\.salto-youth\.net/tools/european-training-calendar/training/[^"]+)"'
)
_APPLY_HREF_RE = re.compile(r'href="([^"]+)"[^>]*class="[^"]*callforaction[^"]*"')
_INFOPACK_RE = re.compile(r'INFOPACK.{0,120}?href="([^"]+)"', re.S)
_FORWARDED_RE = re.compile(r"forwarded to (https?://\S+?)\.?\)")
# Párrafo fijo de disclaimer que SALTO mete en TODAS las fichas — bug real encontrado:
# su posición varía según la ficha (a veces antes del bloque "Apply now!"/fecha límite, a
# veces después), así que cortar el cuerpo en su posición se comía la fecha límite real en
# la mitad de los casos (el extractor caía en la estimación por defecto sin avisar). Ahora
# se ELIMINA el párrafo tal cual, sin importar dónde caiga, en vez de truncar ahí.
_DISCLAIMER_RE = re.compile(r"Disclaimer!.*?for the latest information\.", re.S)


def listing_url(today: date) -> str:
    """Filtro: Training Course (`b_activity_type=4`), España (`b_participating_countries=
    country-27`), actividades que empiecen desde hoy. Sin `b_offset`/`b_order`/`b_limit`."""
    return (
        f"{_BASE}{_LISTING_PATH}?b_keyword=&b_funded_by_yia=0&b_country="
        f"&b_participating_countries=country-27&b_activity_type=4"
        f"&b_accessible_for_disabled=0"
        f"&b_begin_date_after_day={today.day}&b_begin_date_after_month={today.month}"
        f"&b_begin_date_after_year={today.year}&b_browse=Search+training+offers"
    )


def _strip_tags(raw_html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


async def fetch_listing(client: httpx.AsyncClient, today: date) -> list[str]:
    """URLs de ficha en la página 1 (orden/offset por defecto), sin duplicados, en el
    orden en que aparecen."""
    r = await client.get(listing_url(today), headers={"User-Agent": _UA}, timeout=20)
    r.raise_for_status()
    seen: set[str] = set()
    urls: list[str] = []
    for m in _DETAIL_RE.finditer(r.text):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


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


async def fetch_opportunity_text(client: httpx.AsyncClient, detail_url: str) -> str | None:
    """Texto en bruto de una ficha (título, tipo, fechas, lugar, descripción + enlaces de
    infopack/inscripción añadidos como texto plano al final), listo para el extractor.
    `None` si la página no tiene la forma esperada — protección ante un cambio de
    estructura del sitio: mejor no procesar nada que procesar basura."""
    r = await client.get(detail_url, headers={"User-Agent": _UA}, timeout=20)
    r.raise_for_status()
    html = r.text
    text = _strip_tags(html)

    # El contenido real (título, tipo, fechas, descripción, Apply now!/fecha límite...)
    # empieza justo después de la promo de suscripción por email que precede a toda ficha.
    promo_idx = text.find("e-mail notifications")
    body = text[promo_idx + len("e-mail notifications"):] if promo_idx > 0 else text
    body = _DISCLAIMER_RE.sub("", body)
    body = body.strip(" .\n")
    if len(body) < 100:
        return None

    lines = [body]

    infopack_m = _INFOPACK_RE.search(html)
    if infopack_m:
        lines.append(f"\nInfopack: {html_lib.unescape(infopack_m.group(1))}")

    apply_m = _APPLY_HREF_RE.search(html)
    if apply_m:
        apply_url = html_lib.unescape(apply_m.group(1))
        if not apply_url.startswith("http"):
            apply_url = _BASE + apply_url
        ext_url = await _resolve_application_url(client, apply_url)
        lines.append(f"\nEnlace de inscripción: {ext_url}")

    lines.append(f"\nFicha original en SALTO-YOUTH: {detail_url}")
    return "\n".join(lines)
