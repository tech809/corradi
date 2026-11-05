"""Expira las oportunidades cuyo plazo de inscripción ya pasó (deja de estar 'open', así
que desaparecen del mapa y de la lista de abiertas). Ya NO manda ningún mensaje (decisión
2026-08-04: el resumen diario por DM se retira sin sustituto -- cada oportunidad nueva ya
se reenvía al momento por `handoff.opportunity()`/`whatsapp_relay.py`, así que un digest
aparte al final del día dejó de aportar nada). El nombre del módulo se conserva por no
tocar el cron ya desplegado (`0 20 * * *`); lo único que hace ahora es esta expiración.

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

log = logging.getLogger("corradi.summary")


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
