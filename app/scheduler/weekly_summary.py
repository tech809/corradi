"""Resumen semanal: cuántas oportunidades nuevas se publicaron esta semana, cuántas siguen
abiertas ahora mismo, y desglose por país y temática. Pensado para el domingo por la tarde.

Ejecutar por cron en la EC2 o EventBridge + Lambda:
    python -m app.scheduler.weekly_summary
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

log = logging.getLogger("corradi.weekly_summary")


async def run() -> None:
    await open_pool()
    try:
        now = datetime.now(ZoneInfo(cfg.timezone))
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        published = await repo.count_published_since(week_start)
        open_count = await repo.count_open()
        countries = await repo.country_breakdown_since(week_start)
        types = await repo.type_breakdown_since(week_start)
        open_opps = await repo.list_open()

        text = pub.format_weekly_full_summary(
            open_count, countries, types, week_start.date(), now.date(), open_opps
        )
        await pub.publish_to_channel(text)

        log.info("Resumen semanal publicado: %s nuevas, %s abiertas.", published, open_count)
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el resumen semanal")
        await alerts.alert("El resumen semanal no se ha publicado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
