"""Recupera las fichas de SALTO-YOUTH que no se rastrearon mientras el cron estuvo caído
(23-sep a 5-nov 2026) y las mete en la BBDD y en la web SIN publicarlas en Telegram,
WhatsApp ni Instagram (pedido explícito 2026-11-05: el atrasado no debe salir en canales).

Hace lo mismo que `scrape_salto` (reintentos + escaneo desde el cursor), pero en vez de
encolar en `salto_backlog`, guarda cada ficha válida directamente como 'open'. También
vacía lo que hubiera pendiente en `salto_backlog` por el mismo camino. Después el cron
diario normal sigue desde el cursor que deja este script.

    python -m app.scheduler.backfill_salto_web            # de verdad
    python -m app.scheduler.backfill_salto_web --dry-run  # solo cuenta, no guarda nada
"""
from __future__ import annotations

import asyncio
import logging
import sys

import httpx
import psycopg

from app import geo, pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.llm import embeddings
from app.scheduler.publish_salto_backlog import _already_published
from app.scheduler.scrape_salto import _MAX_CONSECUTIVE_MISSING, _START_ID
from app.sources import salto_youth as salto

log = logging.getLogger("corradi.backfill_salto_web")
DRY = "--dry-run" in sys.argv


async def _save_web_only(fields: dict, admin_id: int) -> str:
    """Guarda la ficha como abierta (web y mapa) sin ningún paso de publicación social."""
    dup = await _already_published(fields)
    if dup:
        return "dup:" + dup
    if DRY:
        return "would_save"
    fields = dict(fields)
    fields.update(source="salto", submitted_by="SALTO-YOUTH (recuperada, solo web)", submitted_by_id=admin_id)
    vec = fields.pop("_embedding", None)
    if vec is None:
        try:
            vec = await asyncio.to_thread(embeddings.embed, fields["raw_message"])
        except Exception:  # noqa: BLE001 - igual que commit(): sin vector, se rellena luego
            vec = None
    try:
        opp = await repo.insert_project(fields, vec)
    except psycopg.errors.UniqueViolation:
        # Mismo hash que una ficha ya cerrada/vencida (find_by_hash solo mira las abiertas).
        return "dup:closed"
    await repo.log_submission(admin_id, "created", opp["id"])
    try:
        coords = await asyncio.to_thread(geo.geocode, opp.get("location"), opp.get("country_code"))
        if coords:
            await repo.set_coords(opp["id"], *coords)
    except Exception:  # noqa: BLE001
        log.warning("Sin coordenadas para %s", opp["identifier"], exc_info=True)
    return opp["identifier"]


async def _process(client: httpx.AsyncClient, id_num: int, admin_id: int) -> str:
    probe = await salto.probe_id(client, id_num)
    if probe["status"] in ("missing", "error", "draft"):
        if probe["status"] != "missing" and not DRY:
            await repo.upsert_salto_id(id_num, probe["status"])
        return probe["status"]
    html, url = probe["html"], probe["url"]
    if salto.quick_relevance_check(html) is False:
        if not DRY:
            await repo.upsert_salto_id(id_num, "not_relevant")
        return "not_relevant"
    raw_text = await salto.build_opportunity_text(client, html, url)
    if not raw_text:
        if not DRY:
            await repo.upsert_salto_id(id_num, "error")
        return "unexpected_page"
    result = await pipeline.preview(raw_text, submitted_by_id=admin_id)
    if result["status"] != "ready":
        if not DRY:
            await repo.upsert_salto_id(id_num, result["status"])
        return result["status"]
    saved = await _save_web_only(result["fields"], admin_id)
    if not DRY:
        await repo.upsert_salto_id(id_num, "published", saved if saved.startswith("CORRADI") else None)
    log.info("SALTO id %s -> %s (%s)", id_num, saved, result["fields"].get("title"))
    return "saved" if saved.startswith("CORRADI") or saved == "would_save" else "duplicate"


async def run() -> None:
    await open_pool()
    counts: dict[str, int] = {}
    try:
        admin_id = cfg.admin_telegram_ids[0]
        # 1) Lo que hubiera quedado en la cola de publicación.
        from datetime import datetime, timedelta, timezone
        for item in await repo.due_salto_backlog(datetime.now(timezone.utc) + timedelta(days=365)):
            saved = await _save_web_only(item["fields"], admin_id)
            if not DRY:
                await repo.mark_salto_backlog_published(item["id"], saved.removeprefix("dup:"), id_num=item.get("id_num"))
            counts["backlog"] = counts.get("backlog", 0) + 1
            log.info("Backlog %s -> %s", item["url"], saved)
        async with httpx.AsyncClient(timeout=20) as client:
            # 2) Reintentos de borradores/errores.
            for id_num in await repo.list_salto_retry_ids():
                st = await _process(client, id_num, admin_id)
                if st == "missing" and not DRY:
                    await repo.upsert_salto_id(id_num, "gone")
                counts[st] = counts.get(st, 0) + 1
            # 3) Escaneo desde el cursor.
            cursor = await repo.get_salto_scan_cursor(default=_START_ID - 1)
            id_num, miss = cursor + 1, 0
            while miss < _MAX_CONSECUTIVE_MISSING:
                st = await _process(client, id_num, admin_id)
                miss = miss + 1 if st == "missing" else 0
                counts[st] = counts.get(st, 0) + 1
                id_num += 1
            if not DRY:
                await repo.set_salto_scan_cursor(max(id_num - 1 - _MAX_CONSECUTIVE_MISSING, cursor))
        log.info("Recuperación SALTO (%s): %s, desde id %s hasta %s",
                 "simulación" if DRY else "real", counts, cursor + 1, id_num - 1)
        print(counts)
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
