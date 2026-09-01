"""Rellena el vector de deduplicación de las fichas que se publicaron sin él (p.ej.
porque Gemini devolvía 429 en ese momento — ver `pipeline.commit`).

Ejecutar a mano cuando haga falta:
    python -m app.scheduler.backfill_embeddings           # solo las abiertas
    python -m app.scheduler.backfill_embeddings --todas    # también cerradas/expiradas

Va despacio a propósito (1 embedding/segundo) para no volver a tocar el cupo por minuto.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.llm import embeddings

log = logging.getLogger("corradi.backfill_embeddings")


async def run(only_open: bool = True) -> None:
    await open_pool()
    try:
        pending = await repo.list_without_embedding(only_open=only_open)
        if not pending:
            log.info("Nada que rellenar: todas las fichas tienen vector.")
            return
        log.info("Generando embedding de %s fichas (1/s)…", len(pending))
        ok = fail = 0
        for i, row in enumerate(pending):
            try:
                vec = await asyncio.to_thread(embeddings.embed, row["raw_message"])
                await repo.set_embedding(row["id"], vec)
                ok += 1
                log.info("  ✓ %s · %s", row["identifier"], (row["title"] or "")[:45])
            except Exception as e:  # noqa: BLE001
                fail += 1
                log.warning("  ✗ %s · %s (%s)", row["identifier"], (row["title"] or "")[:45], e)
            if i < len(pending) - 1:
                await asyncio.sleep(1)
        log.info("Listo: %s con vector, %s pendientes (reintenta más tarde).", ok, fail)
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run(only_open="--todas" not in sys.argv))
