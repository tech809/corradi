"""Aviso persistente al responsable de Instagram cuando Meta invalida el token."""
from __future__ import annotations

import hashlib
import logging

from app import alerts
from app.config import cfg
from app.db import repository as repo

log = logging.getLogger("corradi.instagram_auth")


async def notify_expired() -> None:
    fingerprint = hashlib.sha256(cfg.instagram_token.encode()).hexdigest()
    try:
        if not await repo.claim_instagram_auth_alert(fingerprint):
            return
    except Exception:  # noqa: BLE001
        log.exception("No pude registrar el aviso de credencial de Instagram")
        # Avisar igualmente si falla la tabla de deduplicación.
    recipients = [cfg.instagram_alert_telegram_id] if cfg.instagram_alert_telegram_id else None
    await alerts.alert(
        "Instagram parado: token caducado",
        "Meta rechazó el token (código 190). Genera uno nuevo en el panel de Meta, "
        "instálalo en INSTAGRAM_LONG_LIVED_TOKEN y ejecuta el barrido de Instagram. "
        "Las oportunidades siguen en cola y no se gastarán reintentos.",
        recipient_ids=recipients,
    )
