"""Barrido de la cola de Instagram: red de seguridad para lo que no salió al instante desde
`pipeline.commit()` (fallo puntual de la API, token caducado, etc.). Publica TODO lo
pendiente en cada pasada (sin tope diario, a petición del usuario) — pensado para lanzarse
cada 2 horas por cron, no una vez al día como el resumen de Telegram.

Ejecutar por cron en la EC2:
    python -m app.scheduler.publish_instagram
"""
from __future__ import annotations

import asyncio
import logging

from app import alerts
from app import instagram_auth
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, get_pool, open_pool
from app.publisher import instagram

log = logging.getLogger("corradi.instagram_sweep")


async def run() -> None:
    if not instagram.is_configured():
        log.info("Instagram no configurado — nada que hacer.")
        return
    await open_pool()
    try:
        # Una conexión mantiene el bloqueo durante todo el barrido. Así cron y una
        # ejecución manual no publican simultáneamente las mismas filas.
        async with get_pool().connection() as lock_conn:
            cur = await lock_conn.execute(
                "SELECT pg_try_advisory_xact_lock(%s)", (repo.INSTAGRAM_PUBLISH_LOCK_ID,)
            )
            if not (await cur.fetchone())[0]:
                log.info("Ya hay otro barrido de Instagram en marcha.")
                return
            await _run_locked()
    except Exception as e:  # noqa: BLE001
        log.exception("Falló el barrido de Instagram")
        await alerts.alert("Falló el barrido de publicación en Instagram", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


async def _run_locked() -> None:
    try:
        await instagram.check_token()
    except instagram.InstagramTokenExpired:
        log.error("El token de Instagram ha caducado; la cola queda intacta")
        await instagram_auth.notify_expired()
        return
    pending = await repo.list_pending_instagram(cfg.instagram_max_attempts)
    if not pending:
        log.info("Cola de Instagram vacía.")
    else:
        log.info("%s oportunidad(es) pendiente(s) de publicar en Instagram.", len(pending))
    for row in pending:
        if not await instagram.gap_ok():
            log.info(
                "Espaciado mínimo (%s min) aún no cumplido — quedan %s pendiente(s) para el próximo barrido.",
                cfg.instagram_min_gap_minutes, len(pending) - pending.index(row),
            )
            break
        try:
            media_id, story_media_id = await instagram.publish_opportunity(row)
            await repo.mark_instagram_published(row["queue_id"], media_id, story_media_id)
            log.info("Publicada en Instagram: %s", row["identifier"])
        except instagram.InstagramTokenExpired:
            log.error("El token de Instagram ha caducado; la cola queda intacta")
            await instagram_auth.notify_expired()
            break
        except Exception as e:  # noqa: BLE001
            log.exception("Fallo publicando %s en Instagram", row["identifier"])
            await repo.mark_instagram_failed(row["queue_id"], f"{type(e).__name__}: {e}")
            if row["attempts"] + 1 >= cfg.instagram_max_attempts:
                await alerts.alert(
                    f"Instagram: {row['identifier']} agotó los reintentos",
                    str(e), key=f"ig_failed_{row['identifier']}",
                )
    missing_stories = await repo.list_missing_instagram_stories(cfg.instagram_max_attempts)
    for row in missing_stories:
        try:
            story_id = await instagram.publish_story(row)
            await repo.mark_instagram_story_published(row["queue_id"], story_id)
            log.info("Story de Instagram recuperada: %s", row["identifier"])
        except instagram.InstagramTokenExpired:
            log.error("El token de Instagram ha caducado; las stories quedan en cola")
            await instagram_auth.notify_expired()
            break
        except Exception as e:  # noqa: BLE001
            log.warning("Fallo reintentando story de %s: %s", row["identifier"], e)
            await repo.mark_instagram_story_failed(row["queue_id"], f"{type(e).__name__}: {e}")
            if row["attempts"] + 1 >= cfg.instagram_max_attempts:
                await alerts.alert(
                    f"Instagram: story de {row['identifier']} agotó los reintentos",
                    str(e), recipient_ids=(
                        [cfg.instagram_alert_telegram_id] if cfg.instagram_alert_telegram_id else None
                    ),
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # El URL de /me lleva el token.
    asyncio.run(run())
