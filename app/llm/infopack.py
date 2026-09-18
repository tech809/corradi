"""Lectura defensiva de infopacks públicos para enriquecer la ficha editorial.

Falla en silencio de cara al llamador por diseño: un PDF bloqueado nunca debe impedir
publicar una oportunidad. Sí queda registrado en el log, para poder diagnosticar por qué.
"""
from __future__ import annotations

import html
import ipaddress
import io
import logging
import re
import socket
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import httpx

log = logging.getLogger("corradi.infopack")

_MAX_BYTES = 24 * 1024 * 1024
_MAX_TEXT = 45_000
_MAX_REDIRECTS = 10


def _downloadable_url(url: str) -> str:
    """Convierte enlaces compartidos de Drive en descargas legibles cuando es posible."""
    parts = urlsplit(url)
    if parts.hostname not in ("drive.google.com", "docs.google.com"):
        return url
    match = re.search(r"/(?:file/d|document/d|presentation/d)/([^/]+)", parts.path)
    file_id = match.group(1) if match else (parse_qs(parts.query).get("id") or [None])[0]
    if not file_id:
        return url
    return urlunsplit(("https", "drive.google.com", "/uc", urlencode({"export": "download", "id": file_id}), ""))


def _public_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
        return all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, ValueError):
        return False


def _html_text(raw: str) -> str:
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def read(url: str) -> str | None:
    """Devuelve texto acotado de un PDF/HTML público, o None si no es seguro/legible.

    Sigue redirecciones a mano (en vez de dejárselo a httpx) porque un acortador
    (tr.ee, tinyurl...) puede redirigir a un enlace compartido de Drive: si no
    reescribimos CADA salto, acabamos descargando la página HTML del visor de
    Drive en vez del PDF real, y `read()` falla en silencio sin que nada lo indique.
    """
    original_url = url
    url = _downloadable_url(url)
    if not _public_url(url):
        log.warning("infopack.read: URL no pública o no http(s), se descarta: %s", original_url)
        return None
    headers = {"User-Agent": "CorradiBot/1.0 infopack reader"}
    try:
        with httpx.Client(follow_redirects=False, timeout=15.0) as client:
            for _ in range(_MAX_REDIRECTS):
                with client.stream("GET", url, headers=headers) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            log.warning("infopack.read: redirección sin Location desde %s", url)
                            return None
                        url = _downloadable_url(str(response.url.join(location)))
                        if not _public_url(url):
                            log.warning("infopack.read: redirección a URL no pública, origen %s", original_url)
                            return None
                        continue
                    response.raise_for_status()
                    if not _public_url(str(response.url)):
                        log.warning("infopack.read: URL final no pública, origen %s", original_url)
                        return None
                    buf = bytearray()
                    too_big = False
                    for chunk in response.iter_bytes():
                        buf.extend(chunk)
                        if len(buf) > _MAX_BYTES:
                            too_big = True
                            break
                    if too_big:
                        log.warning("infopack.read: supera %d bytes, origen %s", _MAX_BYTES, original_url)
                        return None
                    content_type = response.headers.get("content-type", "").lower()
                break
            else:
                log.warning("infopack.read: demasiadas redirecciones (>%d), origen %s", _MAX_REDIRECTS, original_url)
                return None
        data = bytes(buf)
        if "pdf" in content_type or data.startswith(b"%PDF"):
            from pypdf import PdfReader
            pages = []
            for page in PdfReader(io.BytesIO(data)).pages[:80]:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
        elif "html" in content_type or "text/" in content_type:
            text = _html_text(data.decode("utf-8", errors="ignore"))
        else:
            log.warning("infopack.read: content-type no soportado (%s), origen %s", content_type, original_url)
            return None
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) < 120:
            log.warning("infopack.read: texto extraído demasiado corto (%d chars), origen %s", len(text), original_url)
            return None
        return text[:_MAX_TEXT]
    except Exception:  # noqa: BLE001 - enriquecimiento opcional
        log.warning("infopack.read: excepción leyendo %s", original_url, exc_info=True)
        return None
