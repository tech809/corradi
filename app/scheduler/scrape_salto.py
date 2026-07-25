"""Descubre oportunidades nuevas de Training Course en SALTO-YOUTH (España) y avisa por
DM a los admins con una vista previa — NO publica nada sola. Si el admin quiere publicarla
de verdad, reenvía el texto tal cual al bot (mismo flujo Enviar/Modificar/Cancelar que
cualquier otra oportunidad) — cero código nuevo en el bot, misma vía de siempre.

Solo la página 1 del listado, SIN `b_offset`/`b_order`/`b_limit` (prohibidos por el
`robots.txt` del sitio, investigado 2026-07-25) — ver `app/sources/salto_youth.py`.
Reutiliza `pipeline.preview()`: filtra automáticamente duplicados (frecuente — algunos
coordinadores ya mandan oportunidades de SALTO a mano) y fuera de plazo, antes de
molestar a nadie.

Límite conocido y aceptado por el usuario: con solo la página 1 (~10 resultados), si
algún día entraran más de 10 oportunidades nuevas en un solo día, las que caigan fuera de
esa página no se detectarían hasta que "suban" en el orden por defecto.

Ejecutar por cron en la EC2, a mediodía:
    python -m app.scheduler.scrape_salto
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app import alerts, pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import telegram_publisher as pub
from app.sources import salto_youth as salto

log = logging.getLogger("corradi.scrape_salto")


async def _notify_candidate(raw_text: str, fields: dict) -> None:
    """Dos DMs por candidato (mejor que uno solo largo, para no arriesgar el límite de
    4096 caracteres de Telegram con descripciones extensas): vista previa formateada, y
    el texto en bruto listo para copiar y reenviar al bot. Encontrado en pruebas reales:
    algunas descripciones de SALTO (objetivos, perfil de participantes, costes...) por sí
    solas ya superan el límite — `pub.send_chunked_dm` trocea en líneas enteras si hace
    falta."""
    preview_text = pub.format_opportunity(fields)
    header = "🆕 <b>Nueva oportunidad detectada en SALTO-YOUTH</b>"
    footer = "Si quieres publicarla, reenvía el siguiente texto tal cual al bot:"
    for admin_id in cfg.admin_telegram_ids:
        await pub.send_chunked_dm(admin_id, f"{header}\n\n{preview_text}")
        await pub.send_chunked_dm(admin_id, f"{footer}\n\n{raw_text}")


async def run() -> None:
    if not cfg.admin_telegram_ids:
        log.warning("Sin ADMIN_TELEGRAM_IDS configurado: nadie recibiría los avisos, no ejecuto el scraping.")
        return

    await open_pool()
    try:
        today = datetime.now(ZoneInfo(cfg.timezone)).date()
        admin_id = cfg.admin_telegram_ids[0]
        seen = ready = skipped = 0

        async with httpx.AsyncClient(follow_redirects=True) as client:
            urls = await salto.fetch_listing(client, today)
            for url in urls:
                if not await repo.mark_salto_seen(url):
                    continue
                seen += 1

                try:
                    raw_text = await salto.fetch_opportunity_text(client, url)
                except httpx.HTTPError as e:
                    log.warning("No pude leer la ficha de SALTO %s: %s", url, e)
                    continue
                if not raw_text:
                    log.warning("Ficha de SALTO con forma inesperada, saltada: %s", url)
                    continue

                try:
                    result = await pipeline.preview(raw_text, submitted_by_id=admin_id)
                except Exception:  # noqa: BLE001
                    log.exception("Fallo evaluando la ficha de SALTO %s", url)
                    continue

                if result["status"] != "ready":
                    log.info("SALTO %s descartada (%s)", url, result["status"])
                    skipped += 1
                    continue

                try:
                    await _notify_candidate(raw_text, result["fields"])
                except Exception:  # noqa: BLE001
                    # Que un DM falle (Telegram caído, admin bloqueó al bot...) no debe
                    # tumbar el resto de candidatos del día.
                    log.exception("No pude avisar de la ficha de SALTO %s", url)
                    continue
                ready += 1

        log.info("Scraping SALTO-YOUTH: %s fichas nuevas, %s avisadas, %s descartadas.", seen, ready, skipped)
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el scraping de SALTO-YOUTH")
        await alerts.alert("El scraping diario de SALTO-YOUTH ha fallado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
