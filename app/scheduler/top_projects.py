"""Publica el Top 3 de interacción de los últimos siete días, martes y viernes por cron."""
from __future__ import annotations

import asyncio
import logging

from app import alerts
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import telegram_publisher as pub
from app.publisher import whatsapp_relay

log = logging.getLogger("corradi.top_projects")


async def run() -> None:
    await open_pool()
    try:
        top = await repo.list_top_projects(days=7, limit=3)
        if not top:
            log.info("No hay oportunidades abiertas para construir el Top 3.")
            return
        await pub.publish_to_channel(pub.format_top_projects(top, html=True))
        await whatsapp_relay.send_text(pub.format_top_projects(top, html=False))
        log.info("Top semanal publicado en Telegram y enviado al circuito de WhatsApp: %s", len(top))
    except Exception as e:  # noqa: BLE001
        log.exception("Falló la publicación del Top 3")
        await alerts.alert("El Top 3 no se ha publicado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
