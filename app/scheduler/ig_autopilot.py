"""Piloto automático de Instagram (ver `app/ig_auto/autopilot.py` y `docs/instagram_autopilot.md`).

Cron en la EC2:
    */30 9-23 * * * cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.ig_autopilot >> /tmp/corradi_ig_autopilot.log 2>&1
    15 8 * * *      ... python -m app.scheduler.ig_autopilot --metrics
    30 9 * * 1      ... python -m app.scheduler.ig_autopilot --report

Probar sin publicar:
    python -m app.scheduler.ig_autopilot --dry-run          # genera los ficheros del hueco que toque
    python -m app.scheduler.ig_autopilot --plan 2026-11-16  # planifica un día concreto
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime

from app import alerts
from app.db.pool import close_pool, get_pool, open_pool
from app.ig_auto import autopilot as ap
from app.publisher import instagram as ig

log = logging.getLogger("corradi.scheduler.ig_autopilot")


async def main(args) -> None:
    await open_pool()
    try:
        if not ig.is_configured():
            log.info("Instagram no configurado; nada que hacer")
            return
        async with get_pool().connection() as conn:
            cur = await conn.execute("SELECT pg_try_advisory_lock(%s)", (ap.LOCK_ID,))
            if not (await cur.fetchone())[0]:
                log.info("Otra ejecución en curso")
                return
            try:
                if args.metrics:
                    log.info("Métricas actualizadas: %s", await ap.refresh_metrics())
                elif args.report:
                    await ap.send_report()
                elif args.plan:
                    print(await ap.plan_day(date.fromisoformat(args.plan)))
                else:
                    now = datetime.now(ap.tz())
                    await ap.plan_day(now.date())
                    for line in await ap.run_due(now, dry_run=args.dry_run):
                        print(line)
            finally:
                await conn.execute("SELECT pg_advisory_unlock(%s)", (ap.LOCK_ID,))
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el piloto automático de Instagram")
        await alerts.alert("Piloto de Instagram: error", f"{type(e).__name__}: {e}", key="ig_autopilot")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--metrics", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--plan")
    p.add_argument("--dry-run", action="store_true")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main(p.parse_args()))
