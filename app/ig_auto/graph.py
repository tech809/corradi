"""Llamadas a la Graph API de Instagram: carrusel, Reel, story y métricas.

Reutiliza `_post`/`_get` (token, errores, código 190) de `app/publisher/instagram.py`.
Los ficheros se sirven desde rutas públicas que ya existen en la API, sin tocar `main.py`:
  - imágenes JPEG → `MEDIA_DIR/opportunities/<md5>.jpg` → `/media/opportunities/<md5>.jpg`
  - vídeos MP4    → `MEDIA_DIR/reels/CORRADI-AUTO-<hex>.mp4` → `/ig/CORRADI-AUTO-<hex>/reel.mp4`
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

from app.config import cfg
from app.publisher import instagram as ig

log = logging.getLogger("corradi.ig_auto.graph")

_POLL, _TIMEOUT = 4, 180


def _base() -> str:
    return cfg.instagram_image_base_url.rstrip("/")


def save_image(jpeg: bytes) -> str:
    """Guarda el JPEG y devuelve su URL pública."""
    name = hashlib.md5(jpeg).hexdigest()
    path = Path(cfg.media_dir) / "opportunities" / f"{name}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(jpeg)
    return f"{_base()}/media/opportunities/{name}.jpg"


def video_path(tag: str) -> tuple[Path, str]:
    ident = f"CORRADI-AUTO-{tag}"
    return Path(cfg.media_dir) / "reels" / f"{ident}.mp4", f"{_base()}/ig/{ident}/reel.mp4"


async def _wait(container_id: str) -> None:
    waited = 0
    while waited < _TIMEOUT:
        status = (await ig._get(container_id, {"fields": "status_code"})).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo procesar el contenedor ({status})")
        await asyncio.sleep(_POLL)
        waited += _POLL
    raise RuntimeError("Instagram tardó demasiado en procesar el contenedor")


async def _publish(container_id: str) -> tuple[str, str | None]:
    await _wait(container_id)
    media_id = (await ig._post(f"{cfg.instagram_business_id}/media_publish", {"creation_id": container_id}))["id"]
    try:
        permalink = (await ig._get(media_id, {"fields": "permalink"})).get("permalink")
    except Exception:  # noqa: BLE001
        permalink = None
    return media_id, permalink


async def publish_carousel(image_urls: list[str], caption: str) -> tuple[str, str | None]:
    children = []
    for url in image_urls:
        child = await ig._post(f"{cfg.instagram_business_id}/media", {"image_url": url, "is_carousel_item": "true"})
        children.append(child["id"])
    for c in children:
        await _wait(c)
    parent = await ig._post(f"{cfg.instagram_business_id}/media", {
        "media_type": "CAROUSEL", "children": ",".join(children), "caption": caption,
    })
    return await _publish(parent["id"])


async def publish_reel(video_url: str, caption: str, cover_ms: int,
                      share_to_feed: bool = True) -> tuple[str, str | None]:
    container = await ig._post(f"{cfg.instagram_business_id}/media", {
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false", "thumb_offset": str(cover_ms),
    })
    return await _publish(container["id"])


async def publish_story_image(image_url: str) -> str:
    container = await ig._post(f"{cfg.instagram_business_id}/media", {"image_url": image_url, "media_type": "STORIES"})
    media_id, _ = await _publish(container["id"])
    return media_id


async def media_metrics(media_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    basic = await ig._get(media_id, {"fields": "like_count,comments_count,media_product_type"})
    out["likes"] = basic.get("like_count") or 0
    out["comments"] = basic.get("comments_count") or 0
    ins = await ig._get(f"{media_id}/insights", {"metric": "reach,saved,shares,views,total_interactions"})
    for item in ins.get("data", []):
        out[item["name"]] = (item.get("values") or [{}])[0].get("value", 0) or 0
    return out


async def account() -> dict[str, Any]:
    return await ig._get("me", {"fields": "followers_count,media_count"})
