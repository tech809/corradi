"""API FastAPI: catálogo de oportunidades (lectura) + mapa público.

⚠️ Esta API es PÚBLICA (se expone en internet para servir el mapa). Por eso la
serialización usa **lista blanca** de campos, nunca lista negra: así, si mañana se añade
una columna a `projects`, no se filtra sola. Los datos de quien envía la oportunidad
(`submitted_by`, `submitted_by_id`) y el mensaje original NO salen nunca de aquí.
"""
from __future__ import annotations

import html
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import geo
from app import pipeline
from app.api import auth
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import instagram, instagram_card

_STATIC = Path(__file__).parent / "static"

# Únicos campos que salen al exterior. Todo lo demás (raw_message, embedding, hash,
# submitted_by, submitted_by_id, source...) se queda dentro.
_PUBLIC_FIELDS = (
    "identifier", "title", "type", "topic", "organiser_name", "summary",
    "country_code", "location", "latitude", "longitude",
    "start_date", "end_date", "application_deadline", "deadline_estimated",
    "infopack_url", "application_url", "max_participants",
    "participant_min_age", "participant_max_age", "cost", "contact_information",
    "detailed_description", "programme_details", "learning_outcomes",
    "participant_profile", "accommodation_details", "covered_costs", "travel_details",
    "eligibility_countries", "infopack_enriched",
    "image_url", "image_credit", "image_source_url", "image_origin",
    "status", "telegram_message_id", "created",
)


_SUBMITTED_BY_RE = re.compile(r"^(.*?)\s*\(@([^)]+)\)\s*$")


def _parse_contributor(submitted_by: str) -> dict[str, str | None]:
    """"Nombre (@usuario)" -> {name, username} para el agradecimiento de /estadisticas.
    "@None" pasa cuando el remitente no tenía username público de Telegram en su momento —
    se enseña el nombre igualmente, solo sin enlace a t.me (no hay a dónde enlazar)."""
    m = _SUBMITTED_BY_RE.match(submitted_by)
    if not m:
        return {"name": submitted_by, "username": None}
    name, username = m.group(1).strip(), m.group(2).strip()
    return {"name": name or username, "username": None if username == "None" else username}


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

# Tipografías autoalojadas del mapa (Sora/Manrope, rediseño 2026-07-28) — @font-face en
# mapa.html las pide en /fonts/*.ttf. Cache larga: el nombre de fichero ya lleva el peso,
# así que un cambio de fuente sería un fichero nuevo, no uno que mute bajo la misma URL.
app.mount("/fonts", StaticFiles(directory=_STATIC / "fonts"), name="fonts")
app.mount("/assets", StaticFiles(directory=_STATIC), name="assets")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _file_etag(path: Path) -> str:
    """ETag a partir de la fecha de modificación y el tamaño: cambia si el fichero cambia."""
    st = path.stat()
    return f'"{int(st.st_mtime)}-{st.st_size}"'


# La raíz es la puerta de entrada editorial/listado. El mapa conserva sus dos URLs
# públicas históricas: los enlaces ya repartidos siguen funcionando sin redirecciones.
@app.get("/", include_in_schema=False)
async def discover(request: Request) -> Response:
    path = _STATIC / "discover.html"
    etag = _file_etag(path)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path, media_type="text/html", headers=headers)


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


@app.get("/proyecto/{identifier}", include_in_schema=False)
async def project_page(identifier: str, request: Request) -> Response:
    """Ficha editorial de una oportunidad; los datos se cargan desde la API pública."""
    if not re.fullmatch(r"CORRADI-\d{4}-\d{4}", identifier):
        raise HTTPException(status_code=404)
    path = _STATIC / "project.html"
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


@app.get("/media/opportunities/{filename}", include_in_schema=False)
async def opportunity_media(filename: str) -> FileResponse:
    """Fotografías aportadas por coordinadores, normalizadas por el bot."""
    if not re.fullmatch(r"[a-f0-9]{32}\.jpg", filename):
        raise HTTPException(status_code=404)
    path = Path(cfg.media_dir) / "opportunities" / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        path, media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
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


class ClickRequest(BaseModel):
    kind: str


@app.post("/api/click")
async def click(payload: ClickRequest) -> dict[str, str]:
    """Beacon de clic en un enlace saliente de una tarjeta (Más info / Form / Infopack).
    Agregado puro, igual que /api/visit: no se guarda a qué oportunidad ni quién clicó,
    solo suma al contador de ese tipo de enlace (repo.bump_click valida `kind`)."""
    await repo.bump_click(payload.kind)
    return {"ok": "1"}


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


# ── Panel de publicación (/publicar) ─────────────────────────────────────────────────────
# Mismo pipeline que el bot de Telegram (preview -> confirmar -> commit), solo que la
# "boca" es una página web en vez de un chat. La identidad es la MISMA (ID numérico de
# Telegram vía el widget de login), así que el límite diario, el antispam, los bloqueos y
# los permisos de editar/borrar funcionan sin tocar nada — ver app/api/auth.py.

# Ficha extraída a la espera de que la persona confirme "Publicar". En memoria y con
# caducidad: el proceso `api` es un único uvicorn sin `--workers`, igual que el rate-limit
# del chat de más arriba. Si la api se reinicia se pierden las pendientes y hay que volver
# a darle a Analizar — molesto pero inofensivo, y evita una tabla para algo efímero.
# NO se manda la ficha al cliente para que la devuelva: si no, alguien podría cambiar el
# `application_url` por un enlace suyo DESPUÉS de ver la vista previa.
_pending_previews: dict[str, tuple[float, int, dict[str, Any]]] = {}
_PENDING_TTL_S = 1800

# Campos de la ficha que se le enseñan a quien la está publicando. Misma disciplina de
# lista blanca que _PUBLIC_FIELDS: nunca `raw_message`, `embedding` ni `hash`.
_PREVIEW_FIELDS = (
    "title", "type", "topic", "organiser_name", "summary",
    "country_code", "location", "start_date", "end_date",
    "application_deadline", "deadline_estimated",
    "infopack_url", "application_url", "max_participants",
    "participant_min_age", "participant_max_age", "cost", "contact_information",
    "detailed_description", "programme_details", "learning_outcomes",
    "participant_profile", "accommodation_details", "covered_costs", "travel_details",
    "eligibility_countries", "infopack_enriched",
    "image_url", "image_credit", "image_source_url", "image_origin",
)


def _sweep_pending() -> None:
    now = time.monotonic()
    for token in [t for t, (exp, _, _) in _pending_previews.items() if exp < now]:
        _pending_previews.pop(token, None)


def _current_user(request: Request) -> dict[str, Any] | None:
    return auth.read_session(request.cookies.get(auth.SESSION_COOKIE))


def _require_user(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Necesitas iniciar sesión.")
    return user


@app.get("/publicar", include_in_schema=False)
async def publicar_page(request: Request) -> Response:
    path = _STATIC / "publicar.html"
    etag = _file_etag(path)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path, media_type="text/html", headers=headers)


@app.get("/api/auth/me")
async def auth_me(request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return {"user": _current_user(request), "bot": cfg.telegram_bot_username}


@app.post("/api/auth/telegram")
async def auth_telegram(payload: dict[str, Any], response: Response) -> dict[str, Any]:
    """Recibe tal cual el objeto que entrega el widget de Telegram y comprueba su firma."""
    user = auth.verify_telegram_login({k: str(v) for k, v in payload.items()})
    if not user:
        raise HTTPException(status_code=401, detail="No he podido verificar tu identidad de Telegram.")
    response.set_cookie(
        auth.SESSION_COOKIE, auth.make_session(user),
        max_age=auth.session_max_age(), httponly=True, samesite="lax",
        # Solo `secure` si el sitio va por HTTPS: en local (http://localhost) una cookie
        # marcada como segura el navegador la descarta sin decir nada.
        secure=(_public_origin() or "").startswith("https"),
    )
    return {"user": {"id": user["id"], "name": user["name"], "username": user["username"]}}


@app.post("/api/auth/logout")
async def auth_logout(response: Response) -> dict[str, str]:
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": "1"}


class SubmitPreview(BaseModel):
    text: str
    corrections: list[str] | None = None


@app.post("/api/submit/preview")
async def submit_preview(payload: SubmitPreview, request: Request) -> dict[str, Any]:
    user = _require_user(request)
    text = (payload.text or "").strip()
    if len(text) < 40:
        raise HTTPException(status_code=400, detail="Pega el texto completo de la oportunidad.")
    if await repo.is_blocked(user["id"]):
        raise HTTPException(status_code=403, detail="Tu cuenta está bloqueada para publicar.")

    result = await pipeline.preview(
        text, user["id"], corrections=payload.corrections or None,
        submitted_by_username=user.get("username"),
    )
    if result["status"] != "ready":
        return _clean(result)

    _sweep_pending()
    token = secrets.token_urlsafe(18)
    _pending_previews[token] = (time.monotonic() + _PENDING_TTL_S, user["id"], result["fields"])
    fields = {k: _clean(result["fields"].get(k)) for k in _PREVIEW_FIELDS}
    return {"status": "ready", "token": token, "fields": fields}


class SubmitCommit(BaseModel):
    token: str


@app.post("/api/submit/commit")
async def submit_commit(payload: SubmitCommit, request: Request) -> dict[str, Any]:
    user = _require_user(request)
    _sweep_pending()
    pending = _pending_previews.get(payload.token)
    # El ID de quien confirma tiene que ser el mismo que el de quien pidió la vista previa:
    # un token robado no sirve para publicar desde otra cuenta.
    if not pending or pending[1] != user["id"]:
        raise HTTPException(status_code=404, detail="Esa ficha ya no está disponible. Analízala otra vez.")
    _pending_previews.pop(payload.token, None)

    username = user.get("username")
    result = await pipeline.commit(
        pending[2], source="web",
        submitted_by=f"{user['name']} (@{username})", submitted_by_id=user["id"],
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error") or "No se pudo guardar.")
    opp = result.get("opp") or {}
    return {
        "status": result["status"], "published": bool(result.get("published")),
        "identifier": opp.get("identifier"), "title": opp.get("title"),
    }


@app.get("/api/mine")
async def api_mine(request: Request, response: Response) -> dict[str, Any]:
    user = _require_user(request)
    response.headers["Cache-Control"] = "no-store"
    rows = await repo.list_all_by_user(user["id"], limit=60)
    out = []
    for row in rows:
        item = {k: _clean(row.get(k)) for k in _PREVIEW_FIELDS}
        item["identifier"] = row.get("identifier")
        item["status"] = row.get("status")
        item["created"] = _clean(row.get("created"))
        out.append(item)
    return {"items": out}


class MineEdit(BaseModel):
    identifier: str
    instruction: str


@app.post("/api/mine/edit")
async def api_mine_edit(payload: MineEdit, request: Request) -> dict[str, Any]:
    user = _require_user(request)
    instruction = (payload.instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Dime qué quieres cambiar.")
    result = await pipeline.edit_published(payload.identifier, instruction, user["id"])
    if result["status"] in ("not_found", "forbidden"):
        raise HTTPException(status_code=404, detail="No puedo editar esa oportunidad.")
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error") or "No pude aplicar el cambio.")
    return {"status": "edited"}


class MineDelete(BaseModel):
    identifier: str


@app.post("/api/mine/delete")
async def api_mine_delete(payload: MineDelete, request: Request) -> dict[str, Any]:
    user = _require_user(request)
    result = await pipeline.delete_published(payload.identifier, user["id"])
    if result["status"] in ("not_found", "forbidden"):
        raise HTTPException(status_code=404, detail="No puedo eliminar esa oportunidad.")
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error") or "No pude eliminarla.")
    return {"status": result["status"]}


@app.get("/estadisticas", include_in_schema=False)
async def estadisticas_page(request: Request) -> Response:
    """Página secundaria: asociaciones, archivo de cerradas y línea de tiempo/países
    (docs/ideas_futuras_web.md #9-#12/#26/#28, consolidados en una sola página para no
    complicar la navegación con 3-4 pestañas nuevas)."""
    path = _STATIC / "estadisticas.html"
    etag = _file_etag(path)
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path, media_type="text/html", headers=headers)


@app.get("/api/stats")
async def api_stats(response: Response) -> dict[str, Any]:
    """Datos agregados para /estadisticas: nada de esto identifica a una persona, son
    recuentos agregados por país/mes/organizador. 5 min de caché: no es información que
    cambie de un minuto a otro como el mapa."""
    response.headers["Cache-Control"] = "public, max-age=300"
    total = await repo.count_total_published()
    open_n = await repo.count_open()
    countries = await repo.country_breakdown_all(limit=40)
    months = await repo.monthly_counts(months=12)
    organisers = await repo.organiser_breakdown(limit=200)
    closed = await repo.list_closed(limit=200)
    visits = await repo.daily_visits_since(days=400)
    total_visits = await repo.get_total_visits()
    clicks = await repo.get_click_counts()
    points = await repo.heatmap_points()
    contributors = await repo.contributors_breakdown()
    return {
        "total_published": total,
        "total_open": open_n,
        "total_visits": total_visits,
        "total_clicks": sum(clicks.values()),
        "clicks_by_kind": clicks,
        "top_countries": [
            {
                "country_code": c["country_code"],
                "country_name": _PAISES_ES.get(c["country_code"], c["country_code"]),
                "n": c["n"],
                "centroid": geo.country_centroid(c["country_code"]),
            }
            for c in countries
        ],
        "monthly": [{"month": m["month"], "n": m["n"]} for m in months],
        "organisers": [
            {"name": o["organiser_name"], "total": o["total"], "open": o["open_n"], "projects": o["projects"]}
            for o in organisers
        ],
        "closed": [_serialize(r) for r in closed],
        "daily_visits": [{"day": v["day"], "n": v["n"]} for v in visits],
        "heatmap_points": [[float(p["latitude"]), float(p["longitude"])] for p in points],
        "contributors": [
            {**_parse_contributor(c["submitted_by"]), "total": c["total"]} for c in contributors
        ],
    }


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


@app.get("/share/{identifier}/story.png", include_in_schema=False)
async def share_story_image(identifier: str) -> Response:
    """Tarjeta vertical para compartir una oportunidad desde la web o el mapa."""
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    png = instagram_card.render_share(row, instagram.days_left_label(row))
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f'inline; filename="corradi-{identifier}.png"',
        },
    )


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

# Nombres de tipo/país en español para el <title>/meta description de la mini-ficha SEO
# (mismo diccionario que usan telegram_publisher.py/whatsapp_cloud.py para el resumen —
# copiado en vez de importado porque main.py es la superficie pública y no debe depender
# de app/publisher/*, que trae sus propias dependencias pesadas de Telegram/WhatsApp).
_TIPOS_ES = {
    "YOUTH_EXCHANGE": "Youth Exchange",
    "TRAINING_COURSE": "Training Course",
    "VOLUNTEERING": "ESC",
}
_PAISES_ES = {
    "ES": "España", "PT": "Portugal", "FR": "Francia", "IT": "Italia", "DE": "Alemania",
    "AT": "Austria", "BE": "Bélgica", "NL": "Países Bajos", "LU": "Luxemburgo", "IE": "Irlanda",
    "PL": "Polonia", "CZ": "Chequia", "SK": "Eslovaquia", "HU": "Hungría", "RO": "Rumanía",
    "BG": "Bulgaria", "GR": "Grecia", "HR": "Croacia", "SI": "Eslovenia", "EE": "Estonia",
    "LV": "Letonia", "LT": "Lituania", "FI": "Finlandia", "SE": "Suecia", "DK": "Dinamarca",
    "NO": "Noruega", "IS": "Islandia", "MT": "Malta", "CY": "Chipre", "TR": "Turquía",
    "RS": "Serbia", "MK": "Macedonia del Norte", "ME": "Montenegro", "BA": "Bosnia y Herzegovina",
    "AL": "Albania", "XK": "Kosovo", "GE": "Georgia", "AM": "Armenia", "UA": "Ucrania",
    "MD": "Moldavia",
}


def _public_origin() -> str | None:
    """Esquema+host del mapa público, reconstruidos de `cfg.map_public_url` (que incluye un
    path propio, p.ej. `.../corradi-erasmus`) — mismo truco que `_short_map_link()` en
    telegram_publisher.py, para no depender de una variable de entorno nueva."""
    if not cfg.map_public_url:
        return None
    root = urlsplit(cfg.map_public_url)
    if not root.scheme or not root.netloc:
        return None
    return f"{root.scheme}://{root.netloc}"


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    origin = _public_origin()
    sitemap_line = f"Sitemap: {origin}/sitemap.xml\n" if origin else ""
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nDisallow: /api/\n" + sitemap_line,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    """Un <url> por oportunidad abierta (su enlace corto /AAAA-NNNN) + el mapa. Solo abiertas:
    una cerrada ya no tiene nada que ofrecer a quien llegue buscando plaza, y desaparece sola
    del sitemap el día que se cierra — no hace falta borrarla a mano de ningún sitio."""
    origin = _public_origin()
    if not origin:
        raise HTTPException(status_code=404)
    rows = await repo.list_open()
    urls = [
        f"  <url><loc>{origin}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>",
        f"  <url><loc>{origin}/mapa</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>",
    ]
    for r in rows:
        short_id = str(r["identifier"]).removeprefix("CORRADI-")
        if not _SHORT_ID_RE.fullmatch(short_id):
            continue
        urls.append(f"  <url><loc>{origin}/{short_id}</loc><changefreq>daily</changefreq></url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})


def _short_link_page(row: dict[str, Any]) -> str:
    identifier = row["identifier"]
    title = html.escape(row.get("title") or identifier)
    tipo = _TIPOS_ES.get(row.get("type"), row.get("type") or "")
    pais = _PAISES_ES.get(row.get("country_code"), row.get("country_code") or "")
    lugar = f" en {pais}" if pais else ""
    summary = (row.get("summary") or "").strip()
    description = html.escape(f"{tipo}{lugar}. {summary}"[:200].strip()) if summary else html.escape(f"{tipo}{lugar} — Erasmus+ con Corradi".strip())
    deadline = row.get("application_deadline")
    plazo = f"<p class=\"meta\">📅 Plazo: hasta {html.escape(deadline.isoformat())}</p>" if deadline else ""
    map_url = f"/mapa?o={identifier}"
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{title} · Corradi Erasmus+</title>
<meta name="description" content="{description}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="{map_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="4;url={map_url}">
<style>
  body {{ font: 16px/1.5 -apple-system, system-ui, sans-serif; max-width: 560px; margin: 15vh auto 0; padding: 0 24px; color: #1b1b1f; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .meta {{ color: #555; margin: 4px 0; }}
  a.cta {{ display: inline-block; margin-top: 20px; padding: 12px 20px; background: #1b1b1f; color: #fff; border-radius: 10px; text-decoration: none; font-weight: 600; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">{html.escape(tipo)}{html.escape(lugar)}</p>
{plazo}
<a class="cta" href="{map_url}">Ver en el mapa →</a>
</body>
</html>"""


# Enlace corto para compartir a mano (WhatsApp, etc.): "mapa.proactivefuture.eu/2026-0040"
# en vez de la URL con `?o=` — bastante más presentable en un mensaje de texto plano.
# Va al final del fichero y con un patrón MUY concreto (\d{4}-\d{4}) a propósito: FastAPI
# resuelve las rutas en orden de registro, así que cualquier ruta exacta ya definida arriba
# (/mapa, /health, /opportunities...) gana siempre; esta solo atrapa lo que sobra Y además
# encaja en el patrón, así que no puede colisionar con nada existente ni futuro razonable.
#
# Sirve una mini-página propia (título/descripción/OG reales de ESA oportunidad) en vez de
# un 302 directo al mapa: un 302 no lleva metadatos indexables, así que un buscador o la
# previsualización de un enlace de WhatsApp solo veían el título genérico del mapa entero.
# Redirige sola a los 4s (meta refresh) para quien hace clic desde un chat.
@app.get("/{short_id}", include_in_schema=False)
async def short_link(short_id: str) -> Response:
    if not _SHORT_ID_RE.fullmatch(short_id):
        raise HTTPException(status_code=404)
    identifier = f"CORRADI-{short_id}"
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return RedirectResponse(f"/mapa?o={identifier}", status_code=302)
