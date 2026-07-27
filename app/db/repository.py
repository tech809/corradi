"""Repositorio de oportunidades y lista blanca (async, psycopg3 + pgvector)."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
from psycopg.rows import dict_row

from app.config import cfg
from app.db.pool import get_pool
from app.domain.project import make_hash


def _vec(embedding):
    """pgvector solo adapta arrays numpy (no listas) al tipo vector de Postgres."""
    return np.asarray(embedding, dtype=np.float32) if embedding is not None else None

# Columnas que se escriben al insertar (las normaliza app.domain.project.normalize)
_INSERT_COLS = [
    "identifier", "hash", "title", "type", "topic", "organiser_name", "summary", "raw_message",
    "country_code", "location", "start_date", "end_date", "application_deadline",
    "deadline_estimated", "infopack_url", "application_url", "max_participants",
    "participant_min_age", "participant_max_age", "cost", "contact_information",
    "status", "source", "submitted_by", "submitted_by_id", "embedding",
]


async def _next_identifier(cur) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"{cfg.identifier_prefix}-{year}-"
    await cur.execute(
        "SELECT identifier FROM projects WHERE identifier LIKE %s ORDER BY identifier DESC LIMIT 1",
        (prefix + "%",),
    )
    row = await cur.fetchone()
    seq = int(row["identifier"].rsplit("-", 1)[1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"


async def insert_project(fields: dict[str, Any], embedding: list[float] | None) -> dict[str, Any]:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            identifier = await _next_identifier(cur)
            row = {
                "identifier": identifier,
                "hash": make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date")),
                "title": fields.get("title") or "(sin título)",
                "type": fields.get("type"),
                "topic": fields.get("topic"),
                "organiser_name": fields.get("organiser_name"),
                "summary": fields.get("summary"),
                "raw_message": fields["raw_message"],
                "country_code": fields.get("country_code"),
                "location": fields.get("location"),
                "start_date": fields.get("start_date"),
                "end_date": fields.get("end_date"),
                "application_deadline": fields.get("application_deadline"),
                "deadline_estimated": fields.get("deadline_estimated", False),
                "infopack_url": fields.get("infopack_url"),
                "application_url": fields.get("application_url"),
                "max_participants": fields.get("max_participants"),
                "participant_min_age": fields.get("participant_min_age"),
                "participant_max_age": fields.get("participant_max_age"),
                "cost": fields.get("cost"),
                "contact_information": fields.get("contact_information"),
                "status": "open",
                "source": fields.get("source"),
                "submitted_by": fields.get("submitted_by"),
                "submitted_by_id": fields.get("submitted_by_id"),
                "embedding": _vec(embedding),
            }
            cols = ", ".join(_INSERT_COLS)
            ph = ", ".join(f"%({c})s" for c in _INSERT_COLS)
            await cur.execute(f"INSERT INTO projects ({cols}) VALUES ({ph}) RETURNING *", row)
            return await cur.fetchone()


async def find_by_hash(hash_: str) -> dict[str, Any] | None:
    """Solo cuenta como duplicado si la que ya existe sigue ABIERTA — una cerrada
    (borrada por el coordinador) o expirada no debe bloquear un reenvío nuevo."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM projects WHERE hash = %s AND status = 'open'", (hash_,)
            )
            return await cur.fetchone()


async def find_similar(embedding: list[float], threshold: float | None = None) -> dict[str, Any] | None:
    """Devuelve la oportunidad ABIERTA más parecida (coseno) si supera el umbral de
    similitud. Solo entre las abiertas: una cerrada o expirada no bloquea el reenvío."""
    threshold = cfg.dedup_threshold if threshold is None else threshold
    v = _vec(embedding)
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, identifier, title, 1 - (embedding <=> %s) AS similarity "
                "FROM projects WHERE embedding IS NOT NULL AND status = 'open' "
                "ORDER BY embedding <=> %s LIMIT 1",
                (v, v),
            )
            row = await cur.fetchone()
    if row and row["similarity"] is not None and row["similarity"] >= threshold:
        return row
    return None


async def find_cross_lang_dup(
    embedding: list[float], country_code: str | None, start_date, threshold: float | None = None
) -> dict[str, Any] | None:
    """Detecta la MISMA oportunidad ABIERTA publicada en otro idioma: busca la más parecida
    ENTRE las abiertas que comparten país y fecha de inicio (señal fuerte) y baja el umbral
    de similitud, porque con país+fecha ya coincidiendo un coseno moderado basta."""
    if not country_code or not start_date:
        return None
    threshold = cfg.dedup_crosslang_threshold if threshold is None else threshold
    v = _vec(embedding)
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, identifier, title, 1 - (embedding <=> %s) AS similarity "
                "FROM projects WHERE embedding IS NOT NULL AND status = 'open' "
                "AND country_code = %s AND start_date = %s "
                "ORDER BY embedding <=> %s LIMIT 1",
                (v, country_code, start_date, v),
            )
            row = await cur.fetchone()
    if row and row["similarity"] is not None and row["similarity"] >= threshold:
        return row
    return None


async def list_open() -> list[dict[str, Any]]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM projects WHERE status = 'open' "
                "ORDER BY application_deadline IS NULL, application_deadline ASC"
            )
            return await cur.fetchall()


async def get_by_identifier(identifier: str) -> dict[str, Any] | None:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM projects WHERE identifier = %s", (identifier,))
            return await cur.fetchone()


async def list_open_by_user(user_id: int) -> list[dict[str, Any]]:
    """Oportunidades ABIERTAS que envió este coordinador (su backlog editable), la más
    reciente arriba — mismo orden que el histórico, para encontrar de un vistazo lo que
    acabas de mandar."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM projects WHERE status = 'open' AND submitted_by_id = %s "
                "ORDER BY created DESC",
                (user_id,),
            )
            return await cur.fetchall()


async def list_all_by_user(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """TODO lo que ha publicado este coordinador, cualquier estado (histórico)."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM projects WHERE submitted_by_id = %s ORDER BY created DESC LIMIT %s",
                (user_id, limit),
            )
            return await cur.fetchall()


async def close_project(identifier: str) -> None:
    """Cierra una oportunidad a petición de quien la publicó (o un admin): deja de estar
    'open', así que desaparece del mapa/lista y de list_open_by_user. No es un DELETE de
    verdad — no borra la fila ni el hash de dedup — y NO retira el mensaje ya publicado
    en el canal de Telegram, eso no se puede deshacer."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE projects SET status = 'closed', updated = now() WHERE identifier = %s",
            (identifier,),
        )


# Campos que el coordinador puede reeditar (los mismos que extrae el LLM). NO se toca
# identifier, hash, submitted_by, telegram_message_id, embedding ni created.
_EDITABLE_COLS = [
    "title", "type", "topic", "organiser_name", "summary", "country_code", "location",
    "start_date", "end_date", "application_deadline", "deadline_estimated",
    "infopack_url", "application_url", "max_participants",
    "participant_min_age", "participant_max_age", "cost", "contact_information",
    "latitude", "longitude",
]


async def update_project(identifier: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Actualiza los campos editables de una oportunidad ya publicada (edición por el
    coordinador). Solo cambia lo que aparezca en `fields`; devuelve la fila actualizada."""
    cols = [c for c in _EDITABLE_COLS if c in fields]
    if not cols:
        return await get_by_identifier(identifier)
    row = {c: fields[c] for c in cols}
    row["identifier"] = identifier
    sets = ", ".join(f"{c} = %({c})s" for c in cols)
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"UPDATE projects SET {sets}, updated = now() WHERE identifier = %(identifier)s RETURNING *",
                row,
            )
            return await cur.fetchone()


async def search(
    *, q: str | None = None, type_: str | None = None, country: str | None = None,
    topic: str | None = None, only_open: bool = True, limit: int = 50,
) -> list[dict[str, Any]]:
    where, params = [], []
    if only_open:
        where.append("status = 'open'")
    if type_:
        where.append("type = %s"); params.append(type_)
    if country:
        where.append("country_code = %s"); params.append(country.upper()[:2])
    if topic:
        where.append("topic ILIKE %s"); params.append(f"%{topic}%")
    if q:
        where.append("(title ILIKE %s OR raw_message ILIKE %s OR topic ILIKE %s)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT * FROM projects {clause} "
                f"ORDER BY application_deadline IS NULL, application_deadline ASC LIMIT %s",
                params,
            )
            return await cur.fetchall()


async def set_coords(project_id, lat: float, lon: float) -> None:
    """Guarda las coordenadas del mapa (se geocodifica una sola vez, al crear la ficha)."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE projects SET latitude = %s, longitude = %s, updated = now() WHERE id = %s",
            (lat, lon, project_id),
        )


async def list_without_coords(only_open: bool = True) -> list[dict[str, Any]]:
    """Fichas sin geocodificar todavía (para el backfill de las creadas antes del mapa)."""
    clause = "AND status = 'open'" if only_open else ""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT id, identifier, title, location, country_code FROM projects "
                f"WHERE (latitude IS NULL OR longitude IS NULL) {clause} ORDER BY created"
            )
            return await cur.fetchall()


async def list_open_geo() -> list[dict[str, Any]]:
    """Oportunidades abiertas que tienen coordenadas (las que se pintan en el mapa)."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM projects WHERE status = 'open' "
                "AND latitude IS NOT NULL AND longitude IS NOT NULL "
                "ORDER BY application_deadline IS NULL, application_deadline ASC"
            )
            return await cur.fetchall()


async def mark_published(project_id, message_id: int | None = None) -> None:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "UPDATE projects SET published_telegram = TRUE, telegram_message_id = %s, updated = now() "
            "WHERE id = %s AND published_telegram = FALSE",
            (message_id, project_id),
        )
        # Contador histórico de publicadas: solo suma si esta ficha no estaba ya publicada
        # (rowcount 0 = ya lo estaba), para que reintentos/reejecuciones no lo inflen.
        if cur.rowcount:
            await conn.execute(
                "INSERT INTO counters (key, value) VALUES ('published', 1) "
                "ON CONFLICT (key) DO UPDATE SET value = counters.value + 1"
            )
        elif message_id is not None:
            # Ya estaba publicada pero llega un message_id (p.ej. republicación): actualiza
            # el enlace sin volver a contar.
            await conn.execute(
                "UPDATE projects SET telegram_message_id = %s, updated = now() WHERE id = %s",
                (message_id, project_id),
            )


# ── Contadores de la web (visitas + publicadas) ──────────────────────────────
async def bump_visit() -> dict[str, int]:
    """Suma 1 a las visitas y devuelve las visitas y el total histórico de publicadas."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO counters (key, value) VALUES ('visits', 1) "
            "ON CONFLICT (key) DO UPDATE SET value = counters.value + 1 RETURNING value"
        )
        visits = (await cur.fetchone())[0]
        cur = await conn.execute("SELECT value FROM counters WHERE key = 'published'")
        row = await cur.fetchone()
        return {"visits": visits, "published": row[0] if row else 0}


async def expire_past_deadline(today: date) -> int:
    """Expira las oportunidades cuya fecha límite ya llegó (incluido el propio día: si la
    deadline es hoy, se considera cerrada y no sale en el resumen de esta noche)."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "UPDATE projects SET status = 'expired', updated = now() "
            "WHERE status = 'open' AND application_deadline IS NOT NULL AND application_deadline <= %s",
            (today,),
        )
        return cur.rowcount


# ─── Acceso abierto: bloqueados ─────────────────────────────────────────────
async def is_admin(user_id: int) -> bool:
    return user_id in cfg.admin_telegram_ids


async def is_blocked(user_id: int) -> bool:
    if user_id in cfg.admin_telegram_ids:
        return False
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM blocked_users WHERE telegram_user_id = %s", (user_id,)
        )
        return (await cur.fetchone()) is not None


async def block_user(user_id: int, reason: str, blocked_by: int | None = None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO blocked_users (telegram_user_id, reason, blocked_by) VALUES (%s, %s, %s) "
            "ON CONFLICT (telegram_user_id) DO UPDATE SET "
            "reason = EXCLUDED.reason, blocked_by = EXCLUDED.blocked_by, blocked_at = now()",
            (user_id, reason, blocked_by),
        )


async def unblock_user(user_id: int) -> None:
    async with get_pool().connection() as conn:
        await conn.execute("DELETE FROM blocked_users WHERE telegram_user_id = %s", (user_id,))


# ─── Tracking de envíos (límite diario + detección de spam) ────────────────
async def log_submission(user_id: int, status: str, project_id=None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO submissions (telegram_user_id, status, project_id) VALUES (%s, %s, %s)",
            (user_id, status, project_id),
        )


async def count_created_since(user_id: int, since: datetime) -> int:
    """Cuántas oportunidades ha creado ese usuario desde `since` (para el límite diario)."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT count(*) FROM submissions WHERE telegram_user_id = %s AND status = 'created' "
            "AND created >= %s",
            (user_id, since),
        )
        row = await cur.fetchone()
        return row[0]


async def recent_statuses(user_id: int, limit: int) -> list[str]:
    """Últimos `limit` resultados de ese usuario, más reciente primero (para detectar spam)."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT status FROM submissions WHERE telegram_user_id = %s ORDER BY created DESC LIMIT %s",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def list_published_since(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Oportunidades publicadas con éxito en el rango [start, end) (resumen diario WhatsApp)."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM projects WHERE published_telegram = TRUE "
                "AND created >= %s AND created < %s ORDER BY created ASC",
                (start, end),
            )
            return await cur.fetchall()


async def count_published_since(since: datetime) -> int:
    """Cuántas oportunidades se han publicado con éxito desde `since` (resumen semanal)."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT count(*) FROM projects WHERE published_telegram = TRUE AND created >= %s",
            (since,),
        )
        return (await cur.fetchone())[0]


async def count_open() -> int:
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT count(*) FROM projects WHERE status = 'open'")
        return (await cur.fetchone())[0]


async def country_breakdown_since(since: datetime, limit: int = 5) -> list[dict[str, Any]]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT country_code, count(*) AS n FROM projects "
                "WHERE published_telegram = TRUE AND created >= %s AND country_code IS NOT NULL "
                "GROUP BY country_code ORDER BY n DESC LIMIT %s",
                (since, limit),
            )
            return await cur.fetchall()


async def type_breakdown_since(since: datetime, limit: int = 5) -> list[dict[str, Any]]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT type, count(*) AS n FROM projects "
                "WHERE published_telegram = TRUE AND created >= %s AND type IS NOT NULL "
                "GROUP BY type ORDER BY n DESC LIMIT %s",
                (since, limit),
            )
            return await cur.fetchall()




async def enqueue_salto_backlog(url: str, fields: dict, scheduled_at: datetime) -> None:
    """Cola temporal (`salto_backlog`, ver migración 0007) para publicar el backlog inicial
    de SALTO-YOUTH de forma escalonada. `fields` ya viene normalizado por
    `pipeline.preview()` — se serializa a mano (con `default=str`) porque trae objetos
    `date` que el adaptador jsonb no sabe convertir solo."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO salto_backlog (url, fields, scheduled_at) VALUES (%s, %s::jsonb, %s)",
            (url, json.dumps(fields, default=str), scheduled_at),
        )


async def due_salto_backlog(now: datetime) -> list[dict[str, Any]]:
    """Fichas en cola cuya hora programada ya llegó y aún no se han publicado."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, url, fields FROM salto_backlog "
                "WHERE scheduled_at <= %s AND published_identifier IS NULL "
                "ORDER BY scheduled_at ASC",
                (now,),
            )
            return await cur.fetchall()


async def mark_salto_backlog_published(backlog_id: int, identifier: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE salto_backlog SET published_identifier = %s WHERE id = %s",
            (identifier, backlog_id),
        )


async def list_salto_retry_ids() -> list[int]:
    """IDs de SALTO a reintentar cada día: "borrador" (redirige a login, aún no público) o
    "error" (fallo transitorio de red/extracción la vez anterior) — ambos quedarían fuera
    del rango que el escaneo por cursor vuelve a mirar, así que sin este reintento se
    perderían para siempre (ver migración 0008 y bug real corregido 2026-07-26)."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT id_num FROM salto_ids WHERE status IN ('draft', 'error') ORDER BY id_num"
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def upsert_salto_id(id_num: int, status: str, identifier: str | None = None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO salto_ids (id_num, status, identifier, checked_at) VALUES (%s, %s, %s, now()) "
            "ON CONFLICT (id_num) DO UPDATE SET status = EXCLUDED.status, "
            "identifier = EXCLUDED.identifier, checked_at = now()",
            (id_num, status, identifier),
        )


async def get_salto_scan_cursor(default: int) -> int:
    """Último id_num probado (exista o no) — punto de partida del escaneo de mañana."""
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT last_checked_id FROM salto_scan_cursor WHERE id = 1")
        row = await cur.fetchone()
        return row[0] if row else default


async def set_salto_scan_cursor(last_checked_id: int) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO salto_scan_cursor (id, last_checked_id) VALUES (1, %s) "
            "ON CONFLICT (id) DO UPDATE SET last_checked_id = EXCLUDED.last_checked_id",
            (last_checked_id,),
        )


# ── Cola de Instagram ───────────────────────────────────────────────────────
# Una fila por oportunidad (UNIQUE project_id): 'pending' recién encolada, 'published' ya
# salió, 'failed' se rindió tras agotar los intentos. En Postgres, no en un JSON en git.

async def enqueue_instagram(project_id: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO instagram_posts (project_id) VALUES (%s) "
            "ON CONFLICT (project_id) DO NOTHING",
            (project_id,),
        )


async def get_instagram_queue_id(project_id: str) -> int | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT id FROM instagram_posts WHERE project_id = %s", (project_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def seconds_since_last_instagram_publish() -> float | None:
    """None si nunca se ha publicado nada — el espaciado mínimo no aplica al primer post."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT extract(epoch FROM now() - MAX(updated)) FROM instagram_posts WHERE status = 'published'"
        )
        row = await cur.fetchone()
        return row[0] if row and row[0] is not None else None


async def list_pending_instagram(max_attempts: int, limit: int = 20) -> list[dict[str, Any]]:
    """Pendientes de publicar: 'pending' de siempre, o 'failed' que aún no ha agotado sus
    intentos (para que el barrido periódico los reintente). Prioriza lo que cierra antes —
    una oportunidad de última hora no debe esperar cola detrás de una de dentro de 3 meses.

    Exige `p.status = 'open'`: se encola en cuanto se publica en Telegram, tanto si
    Instagram está configurado como si no — si la cuenta tarda en montarse (semanas) y
    mientras tanto una oportunidad caduca, no tiene sentido publicarla igual cuando por fin
    se active. La cola simplemente la ignora, ya expiró."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT ip.id AS queue_id, ip.attempts, p.* "
                "FROM instagram_posts ip JOIN projects p ON p.id = ip.project_id "
                "WHERE ip.status IN ('pending', 'failed') AND ip.attempts < %s AND p.status = 'open' "
                "ORDER BY p.application_deadline IS NULL, p.application_deadline ASC, ip.created ASC "
                "LIMIT %s",
                (max_attempts, limit),
            )
            return await cur.fetchall()


async def mark_instagram_published(queue_id: int, media_id: str, story_media_id: str | None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE instagram_posts SET status = 'published', media_id = %s, "
            "story_media_id = %s, updated = now() WHERE id = %s",
            (media_id, story_media_id, queue_id),
        )


async def mark_instagram_failed(queue_id: int, error: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE instagram_posts SET status = 'failed', attempts = attempts + 1, "
            "last_error = %s, updated = now() WHERE id = %s",
            (error[:2000], queue_id),
        )
