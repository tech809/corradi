"""Avisos a los administradores por Telegram cuando algo se rompe.

Hasta ahora, si fallaba el resumen de las 20:00, si Gemini agotaba la cuota o si el bot
petaba, solo quedaba rastro en los logs del servidor — es decir, nadie se enteraba hasta
notar que el canal llevaba días mudo. Esto manda un DM a `ADMIN_TELEGRAM_IDS`.

Anti-spam: `key` agrupa avisos repetidos y no reenvía el mismo antes de ALERT_COOLDOWN.
El acumulador vive en memoria, así que solo protege dentro de un mismo proceso (el bot,
que es de larga vida). Los scripts de cron son de un solo uso y mandan un aviso como
mucho por ejecución, así que ahí no hace falta más.
"""
from __future__ import annotations

import html
import logging
import time

from app.config import cfg

log = logging.getLogger("corradi.alerts")

ALERT_COOLDOWN = 3600  # segundos que se silencia un aviso repetido con la misma `key`
_last_sent: dict[str, float] = {}


def _throttled(key: str | None) -> bool:
    if not key:
        return False
    now = time.monotonic()
    last = _last_sent.get(key)
    if last is not None and (now - last) < ALERT_COOLDOWN:
        return True
    _last_sent[key] = now
    return False


async def alert(subject: str, detail: str = "", key: str | None = None) -> None:
    """Avisa a los admins de un fallo. Nunca lanza: un error avisando no debe tumbar
    lo que sea que estuviera fallando ya de por sí."""
    if _throttled(key):
        log.info("Aviso '%s' silenciado (repetido antes de %ss)", subject, ALERT_COOLDOWN)
        return

    text = f"⚠️ <b>{html.escape(subject)}</b>"
    if detail:
        # Se recorta: Telegram corta a 4096 y un stacktrace entero no aporta en el móvil.
        text += f"\n\n<code>{html.escape(detail[:600])}</code>"

    if not cfg.admin_telegram_ids:
        log.warning("Fallo sin destinatario (ADMIN_TELEGRAM_IDS vacío): %s | %s", subject, detail)
        return

    from app.publisher import telegram_publisher as pub

    for admin_id in cfg.admin_telegram_ids:
        try:
            await pub.notify_admin(admin_id, text)
        except Exception:  # noqa: BLE001
            log.exception("No pude avisar al admin %s de: %s", admin_id, subject)
