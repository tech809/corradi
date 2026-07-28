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
from app.db import repository as repo
from app.publisher.telegram_publisher import _compact_dates, _days_left, _est, _flag, _place

log = logging.getLogger("corradi.instagram")

GRAPH = "https://graph.instagram.com"

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

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


def reel_url(identifier: str) -> str:
    base = cfg.instagram_image_base_url.rstrip("/")
    return f"{base}/ig/{identifier}/reel.mp4"


async def gap_ok() -> bool:
    """True si ya pasó el espaciado mínimo desde la última publicación (o si es la primera
    vez). Sin tope diario — solo evita que 2 posts salgan casi seguidos si dos oportunidades
    se confirman con minutos de diferencia."""
    elapsed = await repo.seconds_since_last_instagram_publish()
    return elapsed is None or elapsed >= cfg.instagram_min_gap_minutes * 60


def days_left_label(opp: dict[str, Any]) -> str:
    """'quedan N días' / 'cierra mañana' / 'cierra hoy' — misma lógica que el canal/mapa.
    Para la STORY: es contenido efímero (24h), tiene sentido que hable en relativo."""
    deadline = opp.get("application_deadline")
    return _days_left(deadline) if deadline else "inscripción abierta"


def deadline_date_label(opp: dict[str, Any]) -> str:
    """'3 de octubre' — fecha absoluta, para el FEED: un post se queda ahí semanas, y
    "quedan 2 días" deja de ser cierto en cuanto pasa el tiempo. La fecha absoluta es
    coherente la vea quien la vea, cuando la vea."""
    d = opp.get("application_deadline")
    if not d:
        return "inscripción abierta"
    if isinstance(d, str):
        y, m, day = (int(x) for x in d.split("-"))
    else:
        y, m, day = d.year, d.month, d.day
    return f"{day} de {_MESES[m - 1]}"


def build_caption(opp: dict[str, Any]) -> str:
    lead = _flag(opp.get("country_code")) or "🌍"
    lines = [f"{lead} {opp['title']}", ""]

    meta_bits = [b for b in [_place(opp), _compact_dates(opp)] if b and b != "fechas por confirmar"]
    if meta_bits:
        lines.append("📍 " + " · 🗓️ ".join(meta_bits))
    if opp.get("topic"):
        lines.append(f"🏷️ Temática: {opp['topic']}")

    if opp.get("summary"):
        lines.append("")
        lines.append(opp["summary"])

    if opp.get("application_deadline"):
        lines.append("")
        lines.append(f"⏳ Fecha límite: {opp['application_deadline']}{_est(opp)} ({days_left_label(opp)})")
    lines.append("📱 Toda la info en el link de la bio")
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


async def _get(path: str, params: dict) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{GRAPH}/{path}", params={**params, "access_token": cfg.instagram_token})
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


_REEL_POLL_INTERVAL = 4  # segundos entre comprobaciones de estado del contenedor de vídeo
_REEL_POLL_TIMEOUT = 120  # Instagram puede tardar bastante en procesar un vídeo, a diferencia de una imagen


async def _wait_video_ready(creation_id: str) -> None:
    """A diferencia de una imagen (lista casi al instante), un contenedor de vídeo/Reel se
    procesa de forma asíncrona en los servidores de Instagram — hay que sondear
    `status_code` hasta que sea FINISHED antes de poder publicarlo. IN_PROGRESS mientras
    tanto; ERROR/EXPIRED significa que no va a llegar a FINISHED nunca, aborta ya."""
    elapsed = 0
    while elapsed < _REEL_POLL_TIMEOUT:
        status = await _get(creation_id, {"fields": "status_code"})
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo procesar el vídeo del Reel (status_code={code})")
        await asyncio.sleep(_REEL_POLL_INTERVAL)
        elapsed += _REEL_POLL_INTERVAL
    raise RuntimeError(f"Timeout esperando a que Instagram procese el vídeo del Reel ({_REEL_POLL_TIMEOUT}s)")


async def publish_reel(opp: dict[str, Any]) -> str:
    """Genera el vídeo del Reel (fotogramas + música, ver `reel_video.py`) y lo publica.
    NO forma parte de la cola con reintentos de `instagram_posts` (a diferencia de feed y
    story): es un extra de mejor esfuerzo — si falla, feed y story ya se publicaron igual y
    no merece la pena la complejidad de una cola aparte solo para esto."""
    if not is_configured():
        raise RuntimeError("Instagram no configurado (falta token/business_id/image_base_url)")

    from pathlib import Path

    from app.publisher import reel_video

    out_path = Path(cfg.media_dir) / "reels" / f"{opp['identifier']}.mp4"
    await asyncio.to_thread(reel_video.render_reel_mp4, opp, out_path)

    caption = build_caption(opp)
    create = await _post(
        f"{cfg.instagram_business_id}/media",
        {
            "media_type": "REELS", "video_url": reel_url(opp["identifier"]), "caption": caption,
            # Sin esto, el Reel se cuela TAMBIÉN en el feed normal, duplicado con el post
            # de imagen que ya sale ahí — a petición expresa: el feed es solo para el post,
            # el Reel se queda en su propia pestaña.
            "share_to_feed": "false",
        },
    )
    creation_id = create["id"]
    log.info("Contenedor de Reel creado: %s (%s)", creation_id, opp["identifier"])

    await _wait_video_ready(creation_id)

    publish = await _post(f"{cfg.instagram_business_id}/media_publish", {"creation_id": creation_id})
    log.info("Reel publicado: %s (%s)", publish["id"], opp["identifier"])
    return publish["id"]
