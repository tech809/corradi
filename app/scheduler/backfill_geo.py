"""Rellena latitude/longitude de las oportunidades creadas antes de existir el mapa.

Se ejecuta a mano una sola vez (y luego cuando haga falta):
    python -m app.scheduler.backfill_geo          # solo las abiertas
    python -m app.scheduler.backfill_geo --todas  # también las cerradas/expiradas

Respeta el límite de 1 petición/segundo que pide la política de uso de Nominatim.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app import geo
from app.db import repository as repo
from app.db.pool import close_pool, open_pool

log = logging.getLogger("corradi.backfill_geo")


async def run(only_open: bool = True) -> None:
    await open_pool()
    try:
        pending = await repo.list_without_coords(only_open=only_open)
        if not pending:
            log.info("Nada que geocodificar: todas las fichas ya tienen coordenadas.")
            return
        log.info("Geocodificando %s fichas…", len(pending))
        ok = fail = 0
        for i, row in enumerate(pending):
            coords = await asyncio.to_thread(geo.geocode, row.get("location"), row.get("country_code"))
            if coords:
                await repo.set_coords(row["id"], *coords)
                ok += 1
                log.info("  ✓ %s · %s -> %.4f, %.4f", row["identifier"], row["title"][:45], *coords)
            else:
                fail += 1
                log.warning("  ✗ %s · %s (sin location ni país reconocible)", row["identifier"], row["title"][:45])
            if i < len(pending) - 1:
                await asyncio.sleep(1.1)  # política de uso de Nominatim: máx. 1 req/s
        log.info("Listo: %s geocodificadas, %s sin coordenadas.", ok, fail)
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run(only_open="--todas" not in sys.argv))
