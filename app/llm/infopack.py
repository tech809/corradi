"""Lectura defensiva de infopacks públicos para enriquecer la ficha editorial.

Falla en silencio por diseño: un PDF bloqueado nunca debe impedir publicar una oportunidad.
"""
from __future__ import annotations

import html
import ipaddress
import io
import re
import socket
from urllib.parse import urlsplit

import httpx

_MAX_BYTES = 8 * 1024 * 1024
_MAX_TEXT = 45_000


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
    """Devuelve texto acotado de un PDF/HTML público, o None si no es seguro/legible."""
    if not _public_url(url):
        return None
    try:
        with httpx.Client(follow_redirects=True, timeout=15.0) as client:
            with client.stream("GET", url, headers={"User-Agent": "CorradiBot/1.0 infopack reader"}) as response:
                response.raise_for_status()
                if not _public_url(str(response.url)):
                    return None
                buf = bytearray()
                for chunk in response.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > _MAX_BYTES:
                        return None
                content_type = response.headers.get("content-type", "").lower()
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
            return None
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:_MAX_TEXT] if len(text) >= 120 else None
    except Exception:  # noqa: BLE001 - enriquecimiento opcional
        return None
