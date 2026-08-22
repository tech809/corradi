"""Regenera de forma controlada las fichas anteriores al enriquecimiento editorial.

Uso:
    python -m app.scheduler.backfill_details          # abiertas
    python -m app.scheduler.backfill_details --todas  # también archivo

Hace llamadas reales al LLM y, cuando existe, intenta leer el infopack; por eso nunca se
ejecuta automáticamente durante un despliegue.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app import images
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.llm import extractor
from app.pipeline import today

log = logging.getLogger("corradi.backfill_details")
_DETAIL_KEYS = (
    "detailed_description", "programme_details", "learning_outcomes",
    "participant_profile", "accommodation_details", "covered_costs", "travel_details",
    "eligibility_countries", "infopack_enriched",
    "image_url", "image_credit", "image_source_url", "image_origin",
)


async def run(only_open: bool = True) -> None:
    await open_pool()
    try:
        rows = await repo.list_without_details(only_open)
        log.info("%s fichas pendientes de enriquecer", len(rows))
        for row in rows:
            try:
                fields = await asyncio.to_thread(extractor.extract, row["raw_message"], today())
                if fields.get("is_opportunity") and fields.get("infopack_url"):
                    fields = await asyncio.to_thread(extractor.enrich_from_infopack, fields)
                fields = await asyncio.to_thread(images.enrich, fields)
                details = {key: fields.get(key) for key in _DETAIL_KEYS if fields.get(key) is not None}
                if details:
                    await repo.update_project(row["identifier"], details)
                    log.info("✓ %s · %s", row["identifier"], row["title"][:55])
                else:
                    log.warning("– %s · sin información adicional", row["identifier"])
            except Exception:  # noqa: BLE001 - continúa con la siguiente ficha
                log.exception("✗ %s · no se pudo enriquecer", row["identifier"])
            finally:
                await extractor.flush_usage()
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run(only_open="--todas" not in sys.argv))
