"""Asigna fotografías geográficas a oportunidades existentes sin llamar al LLM.

Uso:
    python -m app.scheduler.backfill_images
    python -m app.scheduler.backfill_images --todas
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from app import images
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool

log = logging.getLogger("corradi.backfill_images")


async def run(only_open: bool = True, limit: int | None = None) -> None:
    if not cfg.pexels_api_key:
        raise SystemExit("Falta PEXELS_API_KEY; no se ha modificado ninguna oportunidad.")
    await open_pool()
    try:
        rows = await repo.list_without_images(only_open)
        if limit is not None:
            rows = rows[:limit]
        log.info("%s oportunidades sin fotografía persistente", len(rows))
        for row in rows:
            enriched = await asyncio.to_thread(images.enrich, dict(row))
            if enriched.get("image_url"):
                await repo.update_project(row["identifier"], {
                    key: enriched.get(key) for key in
                    ("image_url", "image_credit", "image_source_url", "image_origin")
                })
                log.info("✓ %s · %s", row["identifier"], row["location"] or row["country_code"])
            else:
                log.warning("– %s · Pexels no devolvió imagen", row["identifier"])
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--todas", action="store_true", help="incluye el archivo histórico")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(run(only_open=not args.todas, limit=args.limit))
