"""Ingesta incremental de Training Courses SALTO para Corradi World.

Guarda directamente en `world_projects`: no usa el pipeline español, no publica en sus
canales y no toca sus cursores/colas SALTO. El lote pequeño y la pausa entre peticiones
permiten hacer el backfill gradualmente sin golpear el sitio de origen.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date

import httpx

from app import geo
from app.config import cfg
from app.db import world_repository as world_repo
from app.db.pool import close_pool, open_pool
from app.llm import extractor
from app.sources import salto_world
from app.sources import salto_youth as salto

log = logging.getLogger("corradi.salto_world")
_MAX_CONSECUTIVE_MISSING = 8


async def _flush_usage_safely() -> None:
    """Usage accounting is useful, but must never stop the catalogue import."""
    try:
        await extractor.flush_usage()
    except Exception:  # noqa: BLE001
        log.warning("Could not persist World extraction usage", exc_info=True)


async def _process_id(client: httpx.AsyncClient, id_num: int) -> str:
    probe = await salto.probe_id(client, id_num)
    status = probe["status"]
    if status in {"missing", "draft", "error"}:
        if status != "missing":
            await world_repo.upsert_salto_id(id_num, status)
        return status

    raw_html, url = probe["html"], probe["url"]
    relevance = salto_world.quick_relevance_check(raw_html)
    if relevance is False:
        await world_repo.upsert_salto_id(id_num, "not_training_course")
        return "not_training_course"
    if salto_world.is_clearly_closed(raw_html):
        await world_repo.upsert_salto_id(id_num, "closed")
        return "closed"

    raw_text = await salto.build_opportunity_text(client, raw_html, url)
    if not raw_text:
        await world_repo.upsert_salto_id(id_num, "error")
        return "error"
    try:
        fields = await asyncio.to_thread(extractor.extract_world, raw_text, date.today())
    except Exception:  # noqa: BLE001
        log.exception("World extraction failed for SALTO id %s", id_num)
        await world_repo.upsert_salto_id(id_num, "error")
        return "error"
    finally:
        await _flush_usage_safely()

    if not fields.get("is_opportunity") or fields.get("type") != "TRAINING_COURSE":
        await world_repo.upsert_salto_id(id_num, "not_relevant")
        return "not_relevant"
    if fields.get("deadline_in_past"):
        await world_repo.upsert_salto_id(id_num, "expired")
        return "expired"
    if fields.get("is_online"):
        await world_repo.upsert_salto_id(id_num, "online")
        return "online"
    if fields.get("deadline_estimated"):
        # En la edición global no inventamos un plazo para una importación automática:
        # SALTO debe aportar el oficial o la ficha necesita revisión.
        await world_repo.upsert_salto_id(id_num, "missing_deadline")
        return "missing_deadline"

    codes, scope, eligibility_label = salto_world.parse_eligibility(raw_html)
    if eligibility_label:
        fields["eligibility_countries"] = eligibility_label
    fields["source"] = "salto"
    try:
        coords = await asyncio.to_thread(geo.geocode, fields.get("location"), fields.get("country_code"))
        if coords:
            fields["latitude"], fields["longitude"] = coords
    except Exception:  # noqa: BLE001
        log.warning("World geocoding failed for SALTO id %s", id_num, exc_info=True)

    project = await world_repo.upsert_salto_project(fields, id_num, url, codes, scope)
    await world_repo.upsert_salto_id(id_num, "saved", project["identifier"])
    log.info("Saved %s from SALTO id %s", project["identifier"], id_num)
    return "saved"


async def run(limit: int | None = None) -> dict[str, int]:
    await open_pool()
    counts: dict[str, int] = {}
    try:
        batch = max(1, limit or cfg.world_salto_scan_batch)
        async with httpx.AsyncClient(timeout=20) as client:
            # Reintentos acotados: un error antiguo no puede consumir todo el lote.
            for id_num in (await world_repo.list_retry_ids())[:10]:
                status = await _process_id(client, id_num)
                counts[status] = counts.get(status, 0) + 1
                await asyncio.sleep(cfg.world_salto_request_delay)

            cursor = await world_repo.get_scan_cursor(cfg.world_salto_start_id - 1)
            id_num = cursor + 1
            checked = consecutive_missing = 0
            while checked < batch and consecutive_missing < _MAX_CONSECUTIVE_MISSING:
                status = await _process_id(client, id_num)
                counts[status] = counts.get(status, 0) + 1
                consecutive_missing = consecutive_missing + 1 if status == "missing" else 0
                id_num += 1
                checked += 1
                await asyncio.sleep(cfg.world_salto_request_delay)

            if consecutive_missing >= _MAX_CONSECUTIVE_MISSING:
                new_cursor = id_num - 1 - _MAX_CONSECUTIVE_MISSING
            else:
                new_cursor = id_num - 1
            await world_repo.set_scan_cursor(max(cursor, new_cursor))
            log.info("World SALTO scan: %s", counts)
            return counts
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run(args.limit))
