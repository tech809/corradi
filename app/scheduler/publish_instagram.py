"""Barrido de la cola de Instagram: red de seguridad para lo que no salió al instante desde
`pipeline.commit()` (fallo puntual de la API, token caducado, etc.). Publica TODO lo
pendiente en cada pasada (sin tope diario, a petición del usuario) — pensado para lanzarse
cada 2 horas por cron, no una vez al día como el resumen de Telegram.

Ejecutar por cron en la EC2:
    python -m app.scheduler.publish_instagram
"""
from __future__ import annotations

import asyncio
import logging

from app import alerts
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import instagram

log = logging.getLogger("corradi.instagram_sweep")


async def run() -> None:
    if not instagram.is_configured():
        log.info("Instagram no configurado — nada que hacer.")
        return
    await open_pool()
    try:
        pending = await repo.list_pending_instagram(cfg.instagram_max_attempts)
        if not pending:
            log.info("Cola de Instagram vacía.")
            return
        log.info("%s oportunidad(es) pendiente(s) de publicar en Instagram.", len(pending))
        for row in pending:
            try:
                media_id, story_media_id = await instagram.publish_opportunity(row)
                await repo.mark_instagram_published(row["queue_id"], media_id, story_media_id)
                log.info("Publicada en Instagram: %s", row["identifier"])
            except Exception as e:  # noqa: BLE001
                log.exception("Fallo publicando %s en Instagram", row["identifier"])
                await repo.mark_instagram_failed(row["queue_id"], f"{type(e).__name__}: {e}")
                if row["attempts"] + 1 >= cfg.instagram_max_attempts:
                    await alerts.alert(
                        f"Instagram: {row['identifier']} agotó los reintentos",
                        str(e), key=f"ig_failed_{row['identifier']}",
                    )
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el barrido de Instagram")
        await alerts.alert("Falló el barrido de publicación en Instagram", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
