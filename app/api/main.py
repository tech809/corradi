"""API FastAPI: catálogo de oportunidades (lectura) + mapa público.

⚠️ Esta API es PÚBLICA (se expone en internet para servir el mapa). Por eso la
serialización usa **lista blanca** de campos, nunca lista negra: así, si mañana se añade
una columna a `projects`, no se filtra sola. Los datos de quien envía la oportunidad
(`submitted_by`, `submitted_by_id`) y el mensaje original NO salen nunca de aquí.
"""
from __future__ import annotations

import re
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from app import geo
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import instagram, instagram_card

_STATIC = Path(__file__).parent / "static"

# Únicos campos que salen al exterior. Todo lo demás (raw_message, embedding, hash,
# submitted_by, submitted_by_id, source...) se queda dentro.
_PUBLIC_FIELDS = (
    "identifier", "title", "type", "topic", "summary",
    "country_code", "location", "latitude", "longitude",
    "start_date", "end_date", "application_deadline", "deadline_estimated",
    "infopack_url", "application_url", "max_participants",
    "participant_min_age", "participant_max_age", "cost", "contact_information",
    "status", "telegram_message_id", "created",
)


def _clean(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: _clean(row.get(k)) for k in _PUBLIC_FIELDS}
    # Enlace al post original del canal (solo si el canal es público y se guardó el id).
    if cfg.telegram_channel_username and row.get("telegram_message_id"):
        out["channel_url"] = (
            f"https://t.me/{cfg.telegram_channel_username}/{row['telegram_message_id']}"
        )
    else:
        out["channel_url"] = None
    # El pin es aproximado (centro del país) en vez de una ciudad concreta.
    out["approx_location"] = geo.is_country_level(
        row.get("latitude"), row.get("longitude"), row.get("country_code")
    )
    return out


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(
    title="CORRADI-BOT API",
    version="0.2.0",
    description="Catálogo público de oportunidades Erasmus+ de Corradi.",
    lifespan=lifespan,
)
# El webhook de WhatsApp SOLO se monta si WhatsApp está activo. Con la API expuesta a
# internet y `TWILIO_VALIDATE_SIGNATURE=false` por defecto, dejarlo montado permitiría a
# cualquiera hacer POST y colar oportunidades en el canal. Hoy HANDOFF_MODE=none, así que
# ni siquiera existe la ruta.
if cfg.handoff_mode in ("whatsapp_twilio", "whatsapp_cloud"):
    from app.api.twilio_webhook import router as twilio_router

    app.include_router(twilio_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _file_etag(path: Path) -> str:
    """ETag a partir de la fecha de modificación y el tamaño: cambia si el fichero cambia."""
    st = path.stat()
    return f'"{int(st.st_mtime)}-{st.st_size}"'


# URL "bonita" para compartir/publicitar. `/mapa` se conserva como alias (no como
# redirect): cualquier enlace ya repartido (resumen diario de hace días, capturas,
# el propio `channel_url` guardado en la BD) sigue funcionando igual, sin 301 de por
# medio — dos rutas, un único fichero servido.
@app.get("/", include_in_schema=False)
@app.get("/mapa", include_in_schema=False)
@app.get("/corradi-erasmus", include_in_schema=False)
async def mapa(request: Request) -> Response:
    """Mapa interactivo de las oportunidades abiertas.

    `no-cache` = el navegador guarda la copia pero SIEMPRE pregunta si cambió: así una
    versión recién desplegada se ve al instante (con un `max-age` fijo tardaría en llegar).

    El 304 hay que responderlo a mano: `FileResponse` manda el ETag pero NO mira la
    cabecera `If-None-Match`, así que sin esto cada visita se re-descargaba el fichero
    entero — justo lo que la caché pretendía evitar.
    """
    path = _STATIC / "mapa.html"
    etag = _file_etag(path)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path, media_type="text/html", headers=headers)


@app.get("/og.png", include_in_schema=False)
async def og_image() -> FileResponse:
    """Imagen de previsualización al compartir el enlace. Cambia muy de vez en cuando,
    así que se cachea una semana: las redes sociales la piden a menudo."""
    return FileResponse(
        _STATIC / "og.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/api/map")
async def map_data(response: Response) -> dict[str, Any]:
    """Datos del mapa: TODAS las oportunidades abiertas, tengan coordenadas o no.

    Antes se filtraban las que no tenían lat/lon y desaparecían sin dejar rastro. Ahora
    van todas: el mapa pinta las que se pueden situar y la lista las muestra todas, con
    las no situables marcadas — que no se sepa dónde cae no significa que no exista.
    """
    # 60s de caché: absorbe un pico de tráfico (si el canal manda 3.000 personas de golpe,
    # la BD recibe ~1 consulta por minuto en vez de 3.000) y una oportunidad nueva tarda
    # como mucho un minuto en aparecer, que para este caso de uso es instantáneo.
    response.headers["Cache-Control"] = "public, max-age=60"

    rows = await repo.list_open()
    results = [_serialize(r) for r in rows]
    located = sum(1 for r in results if r["latitude"] is not None and r["longitude"] is not None)
    return {
        "count": len(results),
        "located": located,
        "unlocated": len(results) - located,
        "generated": datetime.now().date().isoformat(),
        "channel": cfg.telegram_channel_username or None,
        "results": results,
    }


@app.post("/api/visit")
async def visit() -> dict[str, int]:
    """Suma una visita y devuelve {visits, published} para el pie de estadísticas del mapa.
    Sin caché: cada carga cuenta. Es un contador agregado, no guarda nada de quién visita."""
    return await repo.bump_visit()


# ── Chat del mapa (docs/chatbot_mapa.md) ─────────────────────────────────────────────────
# Rate-limit por IP, ventana deslizante EN MEMORIA: el proceso `api` corre como un único
# uvicorn sin `--workers` (docker/api.Dockerfile), así que un dict basta — no hace falta
# Redis. No se guarda la IP en ningún sitio persistente, solo en este dict que muere con
# el proceso (docs/chatbot_mapa.md §6, privacidad).
_chat_hits: dict[str, list[float]] = {}
_CHAT_WINDOW_DAY = 86400
_CHAT_WINDOW_HOUR = 3600


def _client_ip(request: Request) -> str:
    """La IP real del visitante: la API vive detrás de Caddy, así que `request.client.host`
    sería siempre la IP del contenedor de Caddy — hay que leer X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _chat_rate_limited(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _chat_hits.get(ip, ()) if now - t < _CHAT_WINDOW_DAY]
    hour_hits = [t for t in hits if now - t < _CHAT_WINDOW_HOUR]
    limited = len(hour_hits) >= cfg.chat_rate_limit_per_hour or len(hits) >= cfg.chat_rate_limit_per_day
    if not limited:
        hits.append(now)
    _chat_hits[ip] = hits
    return limited


class ChatRequest(BaseModel):
    pregunta: str


@app.get("/api/chat/status")
async def chat_status() -> dict[str, Any]:
    """El front lo consulta al ABRIR el diálogo del chat (no solo al fallar un envío), para
    decidir si muestra el formulario o el aviso de presupuesto agotado."""
    from app.llm import chat as chat_llm
    return await chat_llm.status()


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
    """Pregunta en lenguaje natural sobre las oportunidades abiertas. Contrato de respuesta
    en docs/chatbot_mapa.md §5: {respuesta, ids, aviso} SIEMPRE, incluso ante rate-limit,
    presupuesto agotado o fallo de Gemini — el front siempre tiene algo que mostrar."""
    from app.llm import chat as chat_llm

    if _chat_rate_limited(_client_ip(request)):
        return {
            "respuesta": "Has hecho demasiadas preguntas seguidas. Espera un poco o usa los filtros del mapa.",
            "ids": [], "aviso": "rate_limit",
        }
    pregunta = (payload.pregunta or "").strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="Falta 'pregunta'")
    return await chat_llm.ask(pregunta)


@app.get("/opportunities")
async def list_opportunities(
    q: str | None = None,
    type: str | None = None,
    country: str | None = None,
    topic: str | None = None,
    only_open: bool = True,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    rows = await repo.search(q=q, type_=type, country=country, topic=topic, only_open=only_open, limit=limit)
    return {"count": len(rows), "results": [_serialize(r) for r in rows]}


@app.get("/opportunities/{identifier}")
async def get_opportunity(identifier: str) -> dict[str, Any]:
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return _serialize(row)


@app.get("/ig/{identifier}/post.png", include_in_schema=False)
async def instagram_post_image(identifier: str) -> Response:
    """Imagen del post de feed (1080x1350), la que la Graph API de Instagram descarga al
    publicar — necesita una URL pública, y esta es nuestra propia API en vez de un repo
    aparte (a diferencia de cómo lo resolvía tur-app, que no tenía servidor propio).
    Fecha ABSOLUTA en el sello ("3 de octubre"): un post de feed se ve semanas después de
    publicarse, y "quedan 2 días" deja de ser cierto — a diferencia de la story."""
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    png = instagram_card.render_feed(row, instagram.deadline_date_label(row))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/ig/{identifier}/story.png", include_in_schema=False)
async def instagram_story_image(identifier: str) -> Response:
    """Imagen de la story (1080x1920). Igual que /post.png pero formato retrato completo."""
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    png = instagram_card.render_story(row, instagram.days_left_label(row))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/ig/{identifier}/reel.mp4", include_in_schema=False)
async def instagram_reel_video(identifier: str) -> FileResponse:
    """El .mp4 del Reel, GENERADO DE ANTEMANO por `bot` (pesado: fotogramas + ffmpeg, ver
    `app/publisher/reel_video.py`) y dejado en el volumen compartido `media_data` — esta
    ruta solo lo sirve tal cual. Nada de generar vídeo al vuelo aquí: sería demasiado lento
    para una petición pública y encima Instagram podría cortar la descarga por timeout."""
    if not identifier.startswith("CORRADI-") or "/" in identifier or ".." in identifier:
        raise HTTPException(status_code=404, detail="No encontrado")
    path = Path(cfg.media_dir) / "reels" / f"{identifier}.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Reel no disponible")
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "public, max-age=3600"})


_SHORT_ID_RE = re.compile(r"^\d{4}-\d{4}$")


# Enlace corto para compartir a mano (WhatsApp, etc.): "mapa.proactivefuture.eu/2026-0040"
# en vez de la URL con `?o=` — bastante más presentable en un mensaje de texto plano.
# Va al final del fichero y con un patrón MUY concreto (\d{4}-\d{4}) a propósito: FastAPI
# resuelve las rutas en orden de registro, así que cualquier ruta exacta ya definida arriba
# (/mapa, /health, /opportunities...) gana siempre; esta solo atrapa lo que sobra Y además
# encaja en el patrón, así que no puede colisionar con nada existente ni futuro razonable.
@app.get("/{short_id}", include_in_schema=False)
async def short_link(short_id: str) -> RedirectResponse:
    if not _SHORT_ID_RE.fullmatch(short_id):
        raise HTTPException(status_code=404)
    identifier = f"CORRADI-{short_id}"
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return RedirectResponse(f"/mapa?o={identifier}", status_code=302)
