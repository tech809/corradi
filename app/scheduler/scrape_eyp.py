"""Ingesta web-only de oportunidades oficiales ESC del Portal Europeo de la Juventud.

No llama al pipeline editorial y no publica en Telegram, Instagram ni WhatsApp. Solo
acepta fichas con deadline explícita, España elegible e inicio futuro.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import cfg
from app import pipeline
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.domain.project import _add_months
from app.sources import european_youth_portal as eyp

log = logging.getLogger("corradi.eyp")


async def run(*, dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    local_now = datetime.now(ZoneInfo(cfg.timezone))
    checked_at = local_now.astimezone(ZoneInfo("UTC"))
    latest = _add_months(local_now.date(), cfg.max_deadline_months)
    async with httpx.AsyncClient() as client:
        rows = await eyp.fetch_open(client, local_now.date())
    candidates = eyp.select_candidates(rows, checked_at, latest)
    if limit is not None:
        candidates = candidates[:max(0, limit)]
    counts = {
        "fetched": len(rows), "selected": len(candidates), "created": 0, "updated": 0,
        "closed": 0, "social_published": 0,
    }
    if dry_run:
        log.info("EYP dry-run: %s", counts)
        return counts

    await open_pool()
    try:
        new_projects = []
        for row in candidates:
            project, created = await repo.upsert_eyp_project(eyp.to_project(row, checked_at))
            counts["created" if created else "updated"] += 1
            if created:
                new_projects.append(project)
        if limit is None:
            counts["closed"] = await repo.close_missing_eyp_projects(
                [str(row["id"]) for row in candidates], checked_at
            )

            published_today = await repo.count_eyp_social_published_on(
                local_now.date(), cfg.timezone
            )
            remaining = max(0, cfg.eyp_social_daily_cap - published_today)
            # Solo entran fichas descubiertas en esta ejecución: el lote web histórico no
            # se drena. Entre las nuevas, primero las más completas y después las urgentes.
            def social_rank(project):
                quality = sum(bool(project.get(key)) for key in (
                    "summary", "detailed_description", "participant_profile",
                    "accommodation_details", "topic", "organiser_name",
                ))
                return (-quality, project.get("application_deadline") or local_now.date())

            for project in sorted(new_projects, key=social_rank)[:remaining]:
                result = await pipeline.publish_existing_eyp(project)
                if result.get("published"):
                    counts["social_published"] += 1
                else:
                    log.error(
                        "ECS %s quedó solo web por fallo social: %s",
                        project["identifier"], result.get("error"),
                    )
        log.info("EYP ingesta y selección social: %s", counts)
        return counts
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx incluye tokens de Telegram/Meta en algunas URLs de diagnóstico; nunca deben
    # terminar en el log del cron.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(asyncio.run(run(dry_run=args.dry_run, limit=args.limit)))
