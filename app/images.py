"""Selección opcional de fotografía editorial con procedencia trazable."""
from __future__ import annotations

import io
import hashlib
import logging
import re
import unicodedata
import uuid
from pathlib import Path

import httpx
import pycountry
from PIL import Image, ImageOps

from app.config import cfg

log = logging.getLogger("corradi.images")


def _queries(fields: dict) -> list[str]:
    """Prioriza el lugar real y amplía solo cuando Pexels no encuentra resultados."""
    location = str(fields.get("location") or "").strip()
    country_code = str(fields.get("country_code") or "").strip().upper()
    country_obj = pycountry.countries.get(alpha_2=country_code) if country_code else None
    country = str(fields.get("country_name") or (country_obj.name if country_obj else country_code)).strip()
    topic = str(fields.get("topic") or "").strip()
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if parts and _normal(parts[-1]) in {_normal(country), _normal(country_code)}:
        parts.pop()
    place = parts[0] if parts else location
    region = parts[-1] if len(parts) > 1 else ""
    candidates = [
        " ".join(x for x in (place, country) if x),
        " ".join(x for x in (region, country) if x) if region else "",
        " ".join(x for x in (country, "travel landscape") if x),
        " ".join(x for x in (topic, country, "Europe") if x),
    ]
    return list(dict.fromkeys(q for q in candidates if q.strip()))


def _normal(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _mentions(photo: dict, place: str) -> bool:
    """Pexels puede devolver otra ciudad; solo aceptamos exactitud si sus metadatos la nombran."""
    needle = _normal(place)
    haystack = _normal(f"{photo.get('alt') or ''} {photo.get('url') or ''}")
    return bool(needle and needle in haystack)


def enrich(fields: dict) -> dict:
    """Busca una imagen Pexels por lugar → país → tema; nunca bloquea la publicación."""
    if fields.get("image_url") or not cfg.pexels_api_key:
        return fields
    try:
        photos = []
        queries = _queries(fields)
        location_parts = [p.strip() for p in str(fields.get("location") or "").split(",") if p.strip()]
        strict_places = [location_parts[0] if location_parts else ""]
        if len(queries) == 4:
            strict_places.append(queries[1].rsplit(" ", 1)[0])
        for index, query in enumerate(queries):
            response = httpx.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "orientation": "landscape", "size": "large", "per_page": 8},
                headers={"Authorization": cfg.pexels_api_key}, timeout=12.0,
            )
            response.raise_for_status()
            photos = response.json().get("photos") or []
            if index < len(strict_places) and strict_places[index]:
                photos = [photo for photo in photos if _mentions(photo, strict_places[index])]
            if photos:
                break
        if not photos:
            return fields
        # Reparto estable dentro de los resultados relevantes: más diversidad sin cambiar
        # de foto en cada carga ni convertir la elección en azar puro.
        seed = str(fields.get("identifier") or fields.get("title") or query).encode()
        shortlist = photos[:3]
        photo = shortlist[int.from_bytes(hashlib.sha256(seed).digest()[:2], "big") % len(shortlist)]
        url = (photo.get("src") or {}).get("large2x") or (photo.get("src") or {}).get("large")
        if not url:
            return fields
        out = dict(fields)
        out.update({
            "image_url": url,
            "image_credit": f"Foto de {photo.get('photographer') or 'Pexels'} en Pexels",
            "image_source_url": photo.get("url"),
            "image_origin": "pexels",
        })
        return out
    except Exception:  # noqa: BLE001 - una foto nunca bloquea la publicación
        log.warning("No pude seleccionar imagen editorial para %s", fields.get("title"), exc_info=True)
        return fields


def save_uploaded(data: bytes) -> str:
    """Normaliza una foto enviada por Telegram y devuelve su URL pública persistente."""
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("La foto supera el límite de 12 MB")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 30_000_000:
            raise ValueError("La resolución de la foto es demasiado grande")
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
        target = Path(cfg.media_dir) / "opportunities"
        target.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}.jpg"
        image.save(target / name, "JPEG", quality=86, optimize=True, progressive=True)
    return f"/media/opportunities/{name}"
