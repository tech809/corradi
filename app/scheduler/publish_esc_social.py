"""Publica en redes (Telegram → WhatsApp → Instagram) el ESC del portal oficial del día.

`scrape_eyp` solo mete las fichas en la web. Este script elige, una vez al día, la mejor
ficha EYP reciente que aún no ha salido en redes y la publica a una hora aleatoria entre
las 17:00 y las 20:00 (hora de `TIMEZONE`). El cupo diario lo sigue garantizando
`repo.publish_esc_with_daily_cap`, así que ejecutarlo dos veces no publica dos ESC.

Los ESC que mandan los gestores al bot no pasan por aquí: se publican al momento, como
un YE o un TC.

Cron en la EC2 (arranca a las 17:00 y espera un rato aleatorio dentro de la franja):
    0 17 * * * cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.publish_esc_social >> /tmp/corradi_esc_social.log 2>&1

Prueba sin esperar:
    python -m app.scheduler.publish_esc_social --now
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool

log = logging.getLogger("corradi.esc_social")

WINDOW_START_HOUR = 17
WINDOW_END_HOUR = 20
# Solo fichas descubiertas en este margen: cubre el hueco entre dos franjas aleatorias
# (hasta ~27 h) sin drenar el lote histórico de la web.
CANDIDATE_MAX_AGE = timedelta(hours=48)


def seconds_until_random_slot(now: datetime, rng: random.Random | None = None) -> float:
    """Segundos a esperar hasta un instante aleatorio entre ahora y las 20:00 de hoy.

    Si ya pasó la franja (o se lanza a mano tarde), devuelve 0.
    """
    rng = rng or random.Random()
    start = now.replace(hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    end = now.replace(hour=WINDOW_END_HOUR, minute=0, second=0, microsecond=0)
    lower = max(now, start)
    if lower >= end:
        return 0.0
    target = lower + timedelta(seconds=rng.uniform(0, (end - lower).total_seconds()))
    return (target - now).total_seconds()


def _social_rank(project: dict[str, Any], today) -> tuple:
    """Primero las más completas; a igualdad, la que cierra antes."""
    quality = sum(bool(project.get(key)) for key in (
        "summary", "detailed_description", "participant_profile",
        "accommodation_details", "topic", "organiser_name",
    ))
    return (-quality, project.get("application_deadline") or today)


async def run(*, wait: bool = True) -> dict[str, Any]:
    if cfg.eyp_social_daily_cap <= 0:
        log.info("ESC social pausado (EYP_SOCIAL_DAILY_CAP=0)")
        return {"published": False, "reason": "paused"}

    tz = ZoneInfo(cfg.timezone)
    if wait:
        delay = seconds_until_random_slot(datetime.now(tz))
        log.info("ESC social: esperando %.0f min", delay / 60)
        await asyncio.sleep(delay)

    now = datetime.now(tz)
    await open_pool()
    try:
        candidates = await repo.list_eyp_social_candidates(now - CANDIDATE_MAX_AGE, now.date())
        if not candidates:
            log.info("ESC social: no hay ESC nuevos del portal para hoy")
            return {"published": False, "reason": "no_candidates"}
        project = min(candidates, key=lambda p: _social_rank(p, now.date()))
        result = await pipeline.publish_existing_eyp(project)
        if result.get("published"):
            log.info("ESC social: publicado %s", project["identifier"])
        else:
            log.error("ESC social: %s quedó solo web: %s", project["identifier"], result.get("error"))
        return {**result, "identifier": project["identifier"]}
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="publica ya, sin esperar a la hora aleatoria")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx incluye tokens de Telegram/Meta en algunas URLs de diagnóstico.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(asyncio.run(run(wait=not args.now)))
