"""Descubre y PUBLICA automáticamente oportunidades de Training Course en SALTO-YOUTH
(España) escaneando IDs secuenciales de fichas (`trainings.salto-youth.net/<id>`) — ver
`app/sources/salto_youth.py` para el porqué de este enfoque (evita el listado paginado,
prohibido por robots.txt para b_offset/b_order/b_limit, y detecta lo nuevo al momento en
vez de con semanas de retraso).

Decisión 2026-07-26: publica DE VERDAD, sin aviso previo por DM — cada ficha que pasa el
filtro barato (Training Course + España) y luego `pipeline.preview()` (dedup, plazo) se
publica sola con `pipeline.commit()`, igual que si un coordinador la hubiera confirmado.

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


async def _process_id(client: httpx.AsyncClient, id_num: int, admin_id: int) -> str:
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

    try:
        commit_result = await pipeline.commit(
            result["fields"], source="salto",
            submitted_by="SALTO-YOUTH (auto)", submitted_by_id=admin_id,
        )
        if commit_result["status"] == "error":
            raise RuntimeError(commit_result.get("error"))
        identifier = commit_result["opp"]["identifier"]
        await repo.upsert_salto_id(id_num, "published", identifier)
        log.info("SALTO id %s publicada como %s (%s)", id_num, identifier, commit_result["status"])
        return "published"
    except Exception:  # noqa: BLE001
        log.exception("Fallo publicando SALTO id %s", id_num)
        await repo.upsert_salto_id(id_num, "error")
        return "error"


async def run() -> None:
    await open_pool()
    try:
        admin_id = cfg.admin_telegram_ids[0]
        async with httpx.AsyncClient(timeout=20) as client:
            retry_ids = await repo.list_salto_retry_ids()
            for id_num in retry_ids:
                status = await _process_id(client, id_num, admin_id)
                if status == "missing":
                    # Un borrador/error que desaparece (retirado, nunca llegó a
                    # publicarse) no debe quedar reintentándose para siempre.
                    await repo.upsert_salto_id(id_num, "gone")
                log.info("SALTO id %s (reintento): %s", id_num, status)

            cursor = await repo.get_salto_scan_cursor(default=_START_ID - 1)
            id_num = cursor + 1
            consecutive_missing = 0
            scanned = published = 0
            while consecutive_missing < _MAX_CONSECUTIVE_MISSING:
                status = await _process_id(client, id_num, admin_id)
                if status == "missing":
                    consecutive_missing += 1
                else:
                    consecutive_missing = 0
                    scanned += 1
                    if status == "published":
                        published += 1
                id_num += 1

            # El cursor se deja justo antes de la racha de "missing" con la que se paró,
            # para que mañana se vuelvan a probar esos últimos IDs (podrían existir ya).
            new_cursor = id_num - 1 - _MAX_CONSECUTIVE_MISSING
            await repo.set_salto_scan_cursor(max(new_cursor, cursor))

            log.info("Escaneo SALTO: %s fichas nuevas evaluadas (%s reintentos de borrador/error), "
                      "%s publicadas, techo alcanzado en id %s.",
                      scanned, len(retry_ids), published, id_num - 1)
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el escaneo de SALTO-YOUTH")
        await alerts.alert("El escaneo diario de SALTO-YOUTH ha fallado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
