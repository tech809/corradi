"""Resumen diario: expira lo vencido y manda por DM a los admins el resumen en formato
WhatsApp de lo publicado HOY (para copiar y pegar a mano en el canal de difusión de
WhatsApp, que no tiene API — ver `docs/`). Ya NO publica en el canal público de Telegram
(decisión 2026-07-25): esa lista de todas las abiertas la sustituye el resumen semanal
por temáticas (`weekly_summary.py`) y el mapa público.

Ejecutar por cron en la EC2 o EventBridge + Lambda:
    python -m app.scheduler.daily_summary
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import alerts
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.summary")


async def run() -> None:
    await open_pool()
    try:
        today_start = datetime.now(ZoneInfo(cfg.timezone)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today = today_start.date()
        expired = await repo.expire_past_deadline(today)
        if expired:
            log.info("Marcadas %s oportunidades como vencidas.", expired)

        today_opps = await repo.list_published_since(today_start, today_start + timedelta(days=1))
        text = pub.format_daily_digest_whatsapp(today_opps)
        for admin_id in cfg.admin_telegram_ids:
            await pub.notify_admin(admin_id, text)
        log.info("Resumen diario (WhatsApp) mandado a %s admin(s): %s publicadas hoy.",
                  len(cfg.admin_telegram_ids), len(today_opps))
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
