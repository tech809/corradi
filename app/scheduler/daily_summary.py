"""Resumen diario: expira lo vencido y publica lo que sigue abierto.

Ejecutar por cron en la EC2 o EventBridge + Lambda:
    python -m app.scheduler.daily_summary
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app import alerts
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import handoff
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.summary")


async def run() -> None:
    await open_pool()
    try:
        today = datetime.now(ZoneInfo(cfg.timezone)).date()
        expired = await repo.expire_past_deadline(today)
        if expired:
            log.info("Marcadas %s oportunidades como vencidas.", expired)

        opps = await repo.list_open()
        await pub.publish_to_channel(pub.format_daily_summary(opps, today))
        await handoff.summary(opps)
        log.info("Resumen diario publicado: %s oportunidades abiertas.", len(opps))
    except Exception as e:  # noqa: BLE001
        # Corre por cron: sin este aviso, un fallo solo deja rastro en /tmp/*.log y el
        # canal se queda mudo sin que nadie se entere.
        log.exception("Falló el resumen diario")
        await alerts.alert("El resumen diario no se ha publicado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
