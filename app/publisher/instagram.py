"""Publica una oportunidad en Instagram (feed + story) vía la Graph API, cuenta Business.

Mismo patrón de llamadas que en `scripts/publish.py` de tur-app (crear contenedor de media
-> esperar -> publicar), pero aquí con httpx async, reutilizando el patrón ya usado en
`whatsapp_cloud.py`. Diferencias clave respecto a tur-app, pensadas para encajar en la
infraestructura que Corradi ya tiene (ver docs/instagram_automation.md):
  - Las imágenes se sirven desde la propia API de Corradi (`GET /ig/{id}/post.png` y
    `/story.png`), no desde un repo aparte de GitHub.
  - No hay `queue.json` en git: el estado vive en la tabla `instagram_posts` (Postgres).
  - El caption se genera del todo por plantilla a partir de los datos ya extraídos — sin
    ningún paso manual ni sesión de escritura por tirada.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import cfg
from app.publisher.telegram_publisher import _compact_dates, _days_left, _est, _flag

log = logging.getLogger("corradi.instagram")

GRAPH = "https://graph.instagram.com"

_HASHTAGS_BY_TYPE = {
    "YOUTH_EXCHANGE": ["#YouthExchange", "#IntercambioJuvenil"],
    "TRAINING_COURSE": ["#TrainingCourse", "#FormaciónJuvenil"],
    "VOLUNTEERING": ["#ECS", "#CuerpoEuropeoDeSolidaridad", "#Voluntariado"],
    "WORKSHOP": ["#Workshop", "#TallerJuvenil"],
}
_HASHTAGS_BASE = ["#ErasmusPlus", "#CorradiErasmus", "#JuventudEuropea", "#OportunidadesErasmus"]


def is_configured() -> bool:
    return bool(cfg.instagram_token and cfg.instagram_business_id and cfg.instagram_image_base_url)


def image_urls(identifier: str) -> tuple[str, str]:
    base = cfg.instagram_image_base_url.rstrip("/")
    return f"{base}/ig/{identifier}/post.png", f"{base}/ig/{identifier}/story.png"


def days_left_label(opp: dict[str, Any]) -> str:
    """'quedan N días' / 'cierra mañana' / 'cierra hoy' — misma lógica que el canal/mapa."""
    deadline = opp.get("application_deadline")
    return _days_left(deadline) if deadline else "inscripción abierta"


def build_caption(opp: dict[str, Any]) -> str:
    lead = _flag(opp.get("country_code")) or "🌍"
    lines = [f"{lead} {opp['title']}", ""]

    meta_bits = [b for b in [opp.get("location"), _compact_dates(opp)] if b and b != "fechas por confirmar"]
    if meta_bits:
        lines.append("📍 " + " · 🗓️ ".join(meta_bits))

    if opp.get("application_deadline"):
        lines.append(f"⏳ {days_left_label(opp).capitalize()} — {opp['application_deadline']}{_est(opp)}")
    lines.append("")
    lines.append("📲 Toda la info y el formulario, en el link de la bio.")
    lines.append("")

    tags = list(_HASHTAGS_BY_TYPE.get(opp.get("type") or "", [])) + _HASHTAGS_BASE
    lines.append(" ".join(tags))
    return "\n".join(lines)


async def _post(path: str, data: dict) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{GRAPH}/{path}", data={**data, "access_token": cfg.instagram_token})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
        return r.json()


async def _create_and_publish(image_url: str, extra: dict) -> str:
    create = await _post(f"{cfg.instagram_business_id}/media", {"image_url": image_url, **extra})
    creation_id = create["id"]
    log.info("Contenedor de Instagram creado: %s", creation_id)

    await asyncio.sleep(5)  # Instagram necesita unos segundos para descargar/procesar la imagen

    publish = await _post(f"{cfg.instagram_business_id}/media_publish", {"creation_id": creation_id})
    return publish["id"]


async def publish_opportunity(opp: dict[str, Any]) -> tuple[str, str | None]:
    """Publica feed + story. Devuelve (media_id, story_media_id) — story_media_id es None
    si falló (un fallo de story NO revierte el post del feed, mismo criterio que tur-app)."""
    if not is_configured():
        raise RuntimeError("Instagram no configurado (falta token/business_id/image_base_url)")

    post_url, story_url = image_urls(opp["identifier"])
    caption = build_caption(opp)

    media_id = await _create_and_publish(post_url, {"caption": caption})
    log.info("Publicado en Instagram (feed): %s (%s)", media_id, opp["identifier"])

    story_media_id = None
    try:
        story_media_id = await _create_and_publish(story_url, {"media_type": "STORIES"})
        log.info("Publicado en Instagram (story): %s (%s)", story_media_id, opp["identifier"])
    except Exception as e:  # noqa: BLE001
        log.warning("El feed se publicó pero la story falló (%s): %s", opp["identifier"], e)

    return media_id, story_media_id
