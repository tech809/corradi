"""Selección opcional de fotografía editorial con procedencia trazable."""
from __future__ import annotations

import logging

import httpx

from app.config import cfg

log = logging.getLogger("corradi.images")


def enrich(fields: dict) -> dict:
    """Busca una imagen Pexels por tema+destino. Sin clave o ante fallo, no cambia nada."""
    if fields.get("image_url") or not cfg.pexels_api_key:
        return fields
    query = " ".join(str(x).strip() for x in (
        fields.get("topic"), fields.get("location"), fields.get("country_code"), "Europe travel"
    ) if x).strip()
    try:
        response = httpx.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "orientation": "landscape", "size": "large", "per_page": 8},
            headers={"Authorization": cfg.pexels_api_key}, timeout=12.0,
        )
        response.raise_for_status()
        photos = response.json().get("photos") or []
        if not photos:
            return fields
        # El resultado superior suele ser el más relevante; Pexels ya aplica moderación y
        # orientación. Guardamos la página original para atribución y auditoría.
        photo = photos[0]
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
