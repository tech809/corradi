"""Persistencia exclusiva de la edición internacional (/world)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row

from app.db.pool import get_pool
from app.domain.project import make_hash


async def _next_identifier(cur) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"WORLD-{year}-"
    await cur.execute(
        "SELECT identifier FROM world_projects WHERE identifier LIKE %s "
        "ORDER BY identifier DESC LIMIT 1",
        (prefix + "%",),
    )
    row = await cur.fetchone()
    seq = int(row["identifier"].rsplit("-", 1)[1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"


async def upsert_salto_project(
    fields: dict[str, Any], source_id: int | None, source_url: str | None,
    eligibility_codes: list[str], eligibility_scope: str,
    source: str = "salto", submitted_by_id: int | None = None,
) -> dict[str, Any]:
    """Inserta una ficha SALTO o refresca la existente sin tocar el catálogo español."""
    columns = [
        "title", "type", "topic", "organiser_name", "summary", "raw_message",
        "country_code", "location", "latitude", "longitude", "start_date", "end_date",
        "application_deadline", "deadline_estimated", "infopack_url", "application_url",
        "max_participants", "participant_min_age", "participant_max_age", "cost",
        "contact_information", "detailed_description", "programme_details",
        "learning_outcomes", "participant_profile", "accommodation_details", "covered_costs",
        "travel_details", "eligibility_countries", "image_url", "image_credit",
        "image_source_url", "image_origin",
    ]
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT identifier FROM world_projects WHERE source_id = %s", (source_id,))
            existing = await cur.fetchone()
            identifier = existing["identifier"] if existing else await _next_identifier(cur)
            row = {name: fields.get(name) for name in columns}
            row.update({
                "identifier": identifier,
                "source_id": source_id,
                "source_url": source_url,
                "hash": make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date")),
                "eligibility_codes": sorted(set(eligibility_codes)),
                "eligibility_scope": eligibility_scope,
                "source": source,
                "submitted_by_id": submitted_by_id,
            })
            insert_cols = [
                "identifier", "source_id", "source_url", "hash", *columns,
                "eligibility_country_codes", "eligibility_scope", "source", "submitted_by_id",
            ]
            values = [
                row.get(c if c != "eligibility_country_codes" else "eligibility_codes")
                for c in insert_cols
            ]
            updates = ", ".join(
                f"{c} = EXCLUDED.{c}" for c in insert_cols
                if c not in {"identifier", "source_id"}
            )
            placeholders = ", ".join(["%s"] * len(insert_cols))
            await cur.execute(
                f"INSERT INTO world_projects ({', '.join(insert_cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT (source_id) DO UPDATE SET {updates}, updated = now(), "
                "last_checked_at = now(), status = 'open' RETURNING *",
                values,
            )
            return await cur.fetchone()


async def insert_manual_project(
    fields: dict[str, Any], submitted_by_id: int,
    eligibility_codes: list[str], eligibility_scope: str,
) -> dict[str, Any]:
    return await upsert_salto_project(
        fields, None, None, eligibility_codes, eligibility_scope,
        source="telegram", submitted_by_id=submitted_by_id,
    )


async def set_telegram_message(identifier: str, message_id: int) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE world_projects SET telegram_message_id = %s WHERE identifier = %s",
            (message_id, identifier),
        )


async def list_open(residence: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ["status = 'open'", "(application_deadline IS NULL OR application_deadline >= current_date)"]
    if residence:
        where.append("(cardinality(eligibility_country_codes) = 0 OR %s = ANY(eligibility_country_codes))")
        params.append(residence.upper())
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM world_projects WHERE " + " AND ".join(where)
                + " ORDER BY application_deadline IS NULL, application_deadline, created DESC",
                params,
            )
            return await cur.fetchall()


async def get_by_identifier(identifier: str) -> dict[str, Any] | None:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM world_projects WHERE identifier = %s", (identifier,))
            return await cur.fetchone()


async def list_retry_ids() -> list[int]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT id_num FROM world_salto_ids WHERE status IN ('draft', 'error') ORDER BY id_num"
        )
        return [row[0] for row in await cur.fetchall()]


async def upsert_salto_id(id_num: int, status: str, identifier: str | None = None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO world_salto_ids (id_num, status, identifier) VALUES (%s, %s, %s) "
            "ON CONFLICT (id_num) DO UPDATE SET status = EXCLUDED.status, "
            "identifier = EXCLUDED.identifier, checked_at = now()",
            (id_num, status, identifier),
        )


async def get_scan_cursor(default: int) -> int:
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT last_checked_id FROM world_salto_scan_cursor WHERE id = 1")
        row = await cur.fetchone()
        return row[0] if row else default


async def set_scan_cursor(last_checked_id: int) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO world_salto_scan_cursor (id, last_checked_id) VALUES (1, %s) "
            "ON CONFLICT (id) DO UPDATE SET last_checked_id = EXCLUDED.last_checked_id",
            (last_checked_id,),
        )
