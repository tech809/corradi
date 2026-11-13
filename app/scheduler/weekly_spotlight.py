"""Mensaje semanal rotativo (datos, récords, destino, Erasmus+, última llamada, estreno).

Elige el tema por la semana del año; si ese tema no tiene datos, prueba el siguiente.
Publica en el canal de Telegram y manda el texto al circuito manual de WhatsApp.

Cron en la EC2 (miércoles 18:00):
    0 18 * * 3 cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.weekly_spotlight >> /tmp/corradi_spotlight.log 2>&1

Ver el mensaje sin publicar nada:
    python -m app.scheduler.weekly_spotlight --dry-run [--theme destino]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from app import alerts, spotlight
from app.config import cfg
from app.db.pool import close_pool, open_pool
from app.publisher import telegram_publisher as pub
from app.publisher import whatsapp_relay

log = logging.getLogger("corradi.weekly_spotlight")


async def build(today, theme: str | None = None, rng: random.Random | None = None) -> tuple[str, str] | None:
    """Devuelve (tema, texto) o None si ningún tema tiene datos."""
    rng = rng or random.Random()
    order = list(spotlight.THEMES)
    start = order.index(theme or spotlight.theme_for(today))
    for name in order[start:] + order[:start]:
        built = await spotlight.body_for(name, today, rng)
        if not built:
            log.info("Tema %s sin datos esta semana; paso al siguiente", name)
            continue
        body, context = built
        hook, closing = await spotlight.write_hook(name, context, rng)
        text = spotlight.compose(hook, body, closing)
        if spotlight.fits(text):
            return name, text
        log.warning("Tema %s demasiado largo; paso al siguiente", name)
    return None


async def run(*, dry_run: bool = False, theme: str | None = None) -> None:
    today = datetime.now(ZoneInfo(cfg.timezone)).date()
    await open_pool()
    try:
        built = await build(today, theme)
        if not built:
            log.info("Ningún tema tiene datos; no se publica nada")
            return
        name, text = built
        if dry_run:
            print(f"--- tema: {name} ---\n[TELEGRAM]\n{spotlight.to_telegram_html(text)}\n\n"
                  f"[WHATSAPP]\n{spotlight.to_whatsapp(text)}")
            return
        await pub.publish_to_channel(spotlight.to_telegram_html(text))
        await whatsapp_relay.send_text(spotlight.to_whatsapp(text))
        log.info("Mensaje semanal publicado (tema %s)", name)
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el mensaje semanal")
        if not dry_run:
            await alerts.alert("El mensaje semanal no se ha publicado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="muestra el mensaje sin publicarlo")
    parser.add_argument("--theme", choices=spotlight.THEMES)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(dry_run=args.dry_run, theme=args.theme))
