"""Repositorio de oportunidades y lista blanca (async, psycopg3 + pgvector)."""
from __future__ import annotations

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
    "identifier", "hash", "title", "type", "topic", "summary", "raw_message",
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
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM projects WHERE hash = %s", (hash_,))
            return await cur.fetchone()


async def find_similar(embedding: list[float], threshold: float | None = None) -> dict[str, Any] | None:
    """Devuelve la oportunidad más parecida (coseno) si supera el umbral de similitud."""
    threshold = cfg.dedup_threshold if threshold is None else threshold
    v = _vec(embedding)
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, identifier, title, 1 - (embedding <=> %s) AS similarity "
                "FROM projects WHERE embedding IS NOT NULL "
                "ORDER BY embedding <=> %s LIMIT 1",
                (v, v),
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


async def mark_published(project_id, message_id: int | None = None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE projects SET published_telegram = TRUE, telegram_message_id = %s, updated = now() "
            "WHERE id = %s",
            (message_id, project_id),
        )


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


async def list_recent_submissions(user_id: int, limit: int = 5) -> list[dict[str, Any]]:
    """Últimos envíos de un usuario con el título de la oportunidad si la creó (para /misenvios)."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT s.status, s.created, p.title FROM submissions s "
                "LEFT JOIN projects p ON p.id = s.project_id "
                "WHERE s.telegram_user_id = %s ORDER BY s.created DESC LIMIT %s",
                (user_id, limit),
            )
            return await cur.fetchall()
