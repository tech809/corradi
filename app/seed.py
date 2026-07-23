"""Carga los mensajes de ejemplo en la base de datos (necesita Postgres en marcha).

    LLM_PROVIDER=fake python -m app.seed     # sin claves
    python -m app.seed                       # con Gemini real (si hay GEMINI_API_KEY)

No pasa por `pipeline.preview()`/`commit()` a propósito: los mensajes de ejemplo son
datos curados, no envíos de un coordinador, así que no hace falta repetir aquí las
comprobaciones pensadas para input de usuario (deadline pasada, deadline demasiado
lejana, límite diario). Sí se geocodifica, igual que `commit()`, para que las fichas
sembradas aparezcan en el mapa y no solo en el canal.
"""
from __future__ import annotations

import asyncio
import logging

from app import geo
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.domain.project import make_hash
from app.llm import embeddings, extractor
from app.samples import SAMPLE_MESSAGES

log = logging.getLogger("corradi.seed")


async def run() -> None:
    await open_pool()
    inserted = skipped = 0
    try:
        for msg in SAMPLE_MESSAGES:
            fields = extractor.extract(msg)
            if not fields.get("is_opportunity"):
                skipped += 1
                continue
            h = make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date"))
            if await repo.find_by_hash(h):
                skipped += 1
                continue
            vec = embeddings.embed(msg)
            if await repo.find_similar(vec):
                skipped += 1
                continue
            fields["source"] = "seed"
            opp = await repo.insert_project(fields, vec)
            coords = await asyncio.to_thread(geo.geocode, opp.get("location"), opp.get("country_code"))
            if coords:
                await repo.set_coords(opp["id"], *coords)
            inserted += 1
            log.info("Insertada %s — %s", opp["identifier"], opp["title"])
    finally:
        await close_pool()
    log.info("Seed completado: %s insertadas, %s omitidas.", inserted, skipped)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
