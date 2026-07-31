"""Publica lo que haya en la cola de SALTO-YOUTH (tabla `salto_backlog`, ver migración 0006
y `app/db/repository.enqueue_salto_backlog`) que ya le toque salir. Publica DE VERDAD (canal
+ mapa), no es una vista previa: las fichas de la cola ya pasaron por `pipeline.preview()`.

Desde 2026-07-31, `scrape_salto.py` encola CADA ficha con una hora aleatoria dentro de su
franja (12:00-13:00 o 17:00-18:00, según el tope diario de mediodía) en vez de publicar
alguna al instante — así que este script tiene que correr con frecuencia DURANTE esas dos
franjas para que la hora aleatoria se note de verdad (si solo corriera una vez por franja, a
la hora en punto, daría exactamente igual que no hubiera aleatoriedad). Cron real: cada ~10
min durante las horas 12 y 17, más una pasada de repesca 5 min después de cerrar cada franja
por si algo se quedó pendiente de una ejecución fallida.

Idempotente y a prueba de ejecuciones perdidas: cada corrida publica TODO lo que esté
programado para <= ahora y siga sin publicar, así que si el cron falla, se pone al día en
la siguiente ejecución en vez de perder esas fichas (nunca las duplica: se marcan
publicadas nada más crearse, antes de intentar el paso de publicación en el canal).

Ejecutar por cron en la EC2 (ver README para la lista completa de horarios):
    python -m app.scheduler.publish_salto_backlog
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app import alerts, pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.domain.project import make_hash
from app.llm import embeddings

log = logging.getLogger("corradi.publish_salto_backlog")


async def _already_published(fields: dict) -> str | None:
    """Repite el mismo chequeo de duplicados de `pipeline.preview()` justo antes de
    publicar de verdad. Bug real encontrado (2026-07-26): las fichas de la cola se vetaron
    hace días con `preview()`, pero `commit()` no vuelve a comprobar duplicados — si
    mientras tanto alguien reenvía a mano esa misma oportunidad al bot, se publicaría dos
    veces sin este chequeo. Devuelve el identifier existente si es duplicado, si no None."""
    existing = await repo.find_by_hash(
        make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date"))
    )
    if existing:
        return existing["identifier"]
    vec = await asyncio.to_thread(embeddings.embed, fields["raw_message"])
    dup = await repo.find_similar(vec)
    if not dup:
        dup = await repo.find_cross_lang_dup(vec, fields.get("country_code"), fields.get("start_date"))
    return dup["identifier"] if dup else None


async def run() -> None:
    await open_pool()
    try:
        now = datetime.now(ZoneInfo(cfg.timezone))
        admin_id = cfg.admin_telegram_ids[0]
        due = await repo.due_salto_backlog(now)
        if not due:
            return

        published = failed = skipped_dup = 0
        for item in due:
            try:
                dup_identifier = await _already_published(item["fields"])
                if dup_identifier:
                    await repo.mark_salto_backlog_published(item["id"], dup_identifier, id_num=item.get("id_num"))
                    skipped_dup += 1
                    log.info("Backlog SALTO %s ya estaba publicada como %s (reenviada a mano "
                              "mientras esperaba en la cola) — saltada, no duplicada.",
                              item["url"], dup_identifier)
                    continue

                result = await pipeline.commit(
                    item["fields"], source="salto",
                    submitted_by="SALTO-YOUTH (backlog)", submitted_by_id=admin_id,
                )
                if result["status"] == "error":
                    raise RuntimeError(result.get("error"))
                identifier = result["opp"]["identifier"]
                await repo.mark_salto_backlog_published(item["id"], identifier, id_num=item.get("id_num"))
                published += 1
                log.info("Publicada del backlog SALTO: %s -> %s (%s)",
                          item["url"], identifier, result["status"])
            except Exception:  # noqa: BLE001
                log.exception("Fallo publicando ficha del backlog SALTO: %s", item["url"])
                failed += 1

        log.info("Backlog SALTO: %s publicadas, %s ya existían (saltadas), %s fallidas de %s pendientes.",
                  published, skipped_dup, failed, len(due))
        if failed:
            await alerts.alert(
                "Publicación del backlog de SALTO con fallos",
                f"{failed} de {len(due)} fichas fallaron al publicar. Revisar logs.",
            )
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el ciclo de publicación del backlog SALTO")
        await alerts.alert("Publicación programada del backlog SALTO falló", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
