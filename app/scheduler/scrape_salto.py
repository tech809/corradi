"""Descubre y PUBLICA automáticamente oportunidades de Training Course en SALTO-YOUTH
(España) escaneando IDs secuenciales de fichas (`trainings.salto-youth.net/<id>`) — ver
`app/sources/salto_youth.py` para el porqué de este enfoque (evita el listado paginado,
prohibido por robots.txt para b_offset/b_order/b_limit, y detecta lo nuevo al momento en
vez de con semanas de retraso).

Decisión 2026-07-26: publica DE VERDAD, sin aviso previo por DM — cada ficha que pasa el
filtro barato (Training Course + España) y luego `pipeline.preview()` (dedup, plazo) se
publica sola, igual que si un coordinador la hubiera confirmado.

Decisión 2026-07-28: como mucho `cfg.salto_scrape_daily_cap` (2 por defecto) salen en la
franja de mediodía — lo que siga pasando el filtro por encima de ese tope se reserva para
la franja de la tarde. Motivo: un día con muchas fichas nuevas a la vez (visto el
2026-07-28: 3 Training Course de golpe) no debe notarse como una ráfaga en el canal — así
como mucho se ven 2 a mediodía y el resto por la tarde.

Decisión 2026-07-31: nada se publica ya en el instante exacto en que corre este script —
TODO se encola en `salto_backlog` con una hora aleatoria dentro de su franja (12:00-13:00
para el tope de mediodía, 17:00-18:00 para el resto), y sale de verdad cuando le toca vía
`publish_salto_backlog` (que ahora corre cada ~10 min durante esas dos franjas). Antes las
2 "directas" salían clavadas a las 12:00:00 en punto cada día — bastaba con mirar el canal
un par de días para notar el patrón. Con hora aleatoria dentro de la franja ya no se nota.

Cada corrida:
1. Reintenta los IDs marcados "draft" (existían pero redirigían a login — puede que ya se
   hayan hecho públicos).
2. Escanea hacia arriba desde el cursor guardado (`salto_scan_cursor`), hasta encontrar
   `_MAX_CONSECUTIVE_MISSING` 404 seguidos (margen de seguridad: alguna ficha "hueco" en
   medio del rango poblado no debe cortar el escaneo antes de tiempo).

Ejecutar por cron en la EC2 (mediodía):
    python -m app.scheduler.scrape_salto
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app import alerts, pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.sources import salto_youth as salto

log = logging.getLogger("corradi.scrape_salto")

# Primer ID nunca visto por nosotros (2026-07-26, ver memoria del proyecto) — solo se usa
# la primera vez, antes de que exista un cursor guardado.
_START_ID = 15121
_MAX_CONSECUTIVE_MISSING = 8


def _random_time_in_window(now: datetime, start_hour: int, end_hour: int) -> datetime:
    """Instante aleatorio dentro de la franja [start_hour, end_hour) de HOY -- para que la
    publicación no caiga siempre clavada a la misma hora en punto (antes: 12:00:00 exacto
    cada día, un patrón que se nota mirando el canal un par de días). Si la franja de hoy ya
    ha pasado, se programa para la misma franja de mañana; si ya estamos dentro de ella
    ahora mismo, el aleatorio arranca desde el instante actual, no desde el inicio (no tiene
    sentido programarlo "en el pasado" de la propia franja)."""
    window_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    window_end = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    if window_end <= now:
        window_start += timedelta(days=1)
        window_end += timedelta(days=1)
    elif window_start < now:
        window_start = now
    span = (window_end - window_start).total_seconds()
    return window_start + timedelta(seconds=random.uniform(0, max(span, 0)))


class _PublishBudget:
    """Cuántas van a la franja de mediodía (12-13h) antes de que el resto pase a la de la
    tarde (17-18h) — compartido entre llamadas a `_process_id` según se van encontrando
    candidatas válidas, no por cada id escaneado."""
    def __init__(self, cap: int) -> None:
        self.remaining = cap


async def _process_id(client: httpx.AsyncClient, id_num: int, admin_id: int, budget: _PublishBudget) -> str:
    """Sonda y procesa un ID. Devuelve el status final (para loggear/contar).

    Bug real encontrado y arreglado (2026-07-26): un fallo transitorio de red en la sonda
    (probe["status"] == "error") no se registraba en absoluto — el ID quedaba por debajo
    del cursor del día siguiente, así que nunca se volvía a intentar, silenciosamente.
    Ahora se guarda como 'error' y se reintenta cada día junto a los borradores."""
    probe = await salto.probe_id(client, id_num)
    if probe["status"] == "missing":
        return "missing"
    if probe["status"] == "error":
        await repo.upsert_salto_id(id_num, "error")
        return "error"
    if probe["status"] == "draft":
        await repo.upsert_salto_id(id_num, "draft")
        return "draft"

    html, url = probe["html"], probe["url"]
    if salto.quick_relevance_check(html) is False:
        await repo.upsert_salto_id(id_num, "not_relevant")
        return "not_relevant"

    raw_text = await salto.build_opportunity_text(client, html, url)
    if not raw_text:
        await repo.upsert_salto_id(id_num, "error")
        return "unexpected_page"

    try:
        result = await pipeline.preview(raw_text, submitted_by_id=admin_id)
    except Exception:  # noqa: BLE001
        log.exception("Fallo evaluando SALTO id %s", id_num)
        await repo.upsert_salto_id(id_num, "error")
        return "error"

    if result["status"] != "ready":
        await repo.upsert_salto_id(id_num, result["status"])
        return result["status"]

    # Nada se publica ya en el instante en que corre este script (ver docstring del módulo,
    # decisión 2026-07-31): SIEMPRE se encola, con hora aleatoria dentro de su franja —
    # mediodía mientras quede presupuesto, tarde para el resto. "queued" (no "draft"/"error")
    # para que `list_salto_retry_ids` no la vuelva a recoger mañana: ya está resuelta, solo
    # pendiente de que le toque salir.
    now = datetime.now(ZoneInfo(cfg.timezone))
    if budget.remaining > 0:
        scheduled_at = _random_time_in_window(now, 12, 13)
        budget.remaining -= 1
    else:
        scheduled_at = _random_time_in_window(now, 17, 18)
    await repo.enqueue_salto_backlog(url, result["fields"], scheduled_at, id_num=id_num)
    await repo.upsert_salto_id(id_num, "queued")
    log.info("SALTO id %s lista, encolada para %s", id_num, scheduled_at.strftime("%H:%M:%S"))
    return "queued"


async def run() -> None:
    await open_pool()
    try:
        admin_id = cfg.admin_telegram_ids[0]
        budget = _PublishBudget(cfg.salto_scrape_daily_cap)
        async with httpx.AsyncClient(timeout=20) as client:
            retry_ids = await repo.list_salto_retry_ids()
            for id_num in retry_ids:
                status = await _process_id(client, id_num, admin_id, budget)
                if status == "missing":
                    # Un borrador/error que desaparece (retirado, nunca llegó a
                    # publicarse) no debe quedar reintentándose para siempre.
                    await repo.upsert_salto_id(id_num, "gone")
                log.info("SALTO id %s (reintento): %s", id_num, status)

            cursor = await repo.get_salto_scan_cursor(default=_START_ID - 1)
            id_num = cursor + 1
            consecutive_missing = 0
            scanned = queued = 0
            while consecutive_missing < _MAX_CONSECUTIVE_MISSING:
                status = await _process_id(client, id_num, admin_id, budget)
                if status == "missing":
                    consecutive_missing += 1
                else:
                    consecutive_missing = 0
                    scanned += 1
                    if status == "queued":
                        queued += 1
                id_num += 1

            # El cursor se deja justo antes de la racha de "missing" con la que se paró,
            # para que mañana se vuelvan a probar esos últimos IDs (podrían existir ya).
            new_cursor = id_num - 1 - _MAX_CONSECUTIVE_MISSING
            await repo.set_salto_scan_cursor(max(new_cursor, cursor))

            log.info("Escaneo SALTO: %s fichas nuevas evaluadas (%s reintentos de borrador/error), "
                      "%s encoladas (tope de %s a la franja de mediodía, resto a la de la tarde), "
                      "techo alcanzado en id %s.",
                      scanned, len(retry_ids), queued, cfg.salto_scrape_daily_cap, id_num - 1)
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el escaneo de SALTO-YOUTH")
        await alerts.alert("El escaneo diario de SALTO-YOUTH ha fallado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
