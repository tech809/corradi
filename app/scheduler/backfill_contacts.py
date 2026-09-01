"""Sanea `contact_information` de las fichas ya guardadas con la misma lógica que
`app.domain.project.clean_contact` (etiquetas colgando sin valor, placeholders, ruido).

Se ejecuta a mano una sola vez (las nuevas ya entran limpias por `normalize()`):
    python -m app.scheduler.backfill_contacts            # muestra qué cambiaría
    python -m app.scheduler.backfill_contacts --apply    # lo aplica
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app.db.pool import close_pool, open_pool, get_pool
from app.domain.project import clean_contact

log = logging.getLogger("corradi.backfill_contacts")


async def run(apply: bool = False) -> None:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            cur = await conn.execute(
                "SELECT id, identifier, title, contact_information FROM projects "
                "WHERE contact_information IS NOT NULL"
            )
            rows = await cur.fetchall()

        cambios = []
        for pid, identifier, title, raw in rows:
            limpio = clean_contact(raw)
            if (limpio or None) != (raw or None):
                cambios.append((pid, identifier, title, raw, limpio))

        if not cambios:
            log.info("Nada que sanear: los %s contactos ya están limpios.", len(rows))
            return

        log.info("%s de %s fichas con contacto a sanear:", len(cambios), len(rows))
        for _pid, identifier, title, raw, limpio in cambios:
            log.info("  %s · %s", identifier, (title or "")[:45])
            log.info("      antes: %r", raw)
            log.info("      ahora: %r", limpio)

        if not apply:
            log.info("Simulación (sin --apply): no se ha tocado nada.")
            return

        async with get_pool().connection() as conn:
            for pid, _identifier, _title, _raw, limpio in cambios:
                await conn.execute(
                    "UPDATE projects SET contact_information = %s, updated = now() WHERE id = %s",
                    (limpio, pid),
                )
        log.info("Aplicado: %s contactos saneados.", len(cambios))
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run(apply="--apply" in sys.argv))
