"""Expira cada noche las oportunidades cuyo plazo de inscripción ya pasó (dejan de estar
'open', así que salen del mapa, de la lista de abiertas y del control de duplicados).
No manda ningún mensaje.

Sustituye a `daily_summary.py` (2026-11-05): ese módulo hacía solo esto desde agosto y
el nombre llevaba a pensar que enviaba un resumen.

Cron en la EC2 (20:00 Madrid):
    python -m app.scheduler.expire_projects
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

log = logging.getLogger("corradi.expire")


async def run() -> None:
    await open_pool()
    try:
        today = datetime.now(ZoneInfo(cfg.timezone)).date()
        expired = await repo.expire_past_deadline(today)
        log.info("Marcadas %s oportunidades como vencidas.", expired)
    except Exception as e:  # noqa: BLE001
        # Corre por cron: sin este aviso, un fallo solo deja rastro en /tmp/*.log y nadie
        # se entera de que las oportunidades vencidas dejaron de cerrarse solas.
        log.exception("Falló la expiración diaria de oportunidades")
        await alerts.alert("La expiración diaria de oportunidades ha fallado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
