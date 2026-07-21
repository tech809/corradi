"""Despachador del handoff a los admins según HANDOFF_MODE.

- telegram        → publica el texto listo para pegar en un grupo privado de Telegram.
- whatsapp_cloud  → envía la oportunidad por WhatsApp Business Cloud API (plantilla).
- none            → no hace nada.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import cfg
from app.publisher import telegram_publisher as tg
from app.publisher import whatsapp_cloud as wa
from app.publisher import whatsapp_twilio as twilio

log = logging.getLogger("corradi.handoff")


async def opportunity(opp: dict[str, Any]) -> None:
    mode = cfg.handoff_mode
    if mode == "telegram":
        await tg.send_to_handoff_group(tg.format_opportunity_whatsapp(opp))
    elif mode == "whatsapp_twilio":
        await twilio.send_opportunity(opp)
    elif mode == "whatsapp_cloud":
        await wa.send_opportunity(opp)
    elif mode != "none":
        log.warning("HANDOFF_MODE desconocido: %s", mode)


async def summary(opps: list[dict[str, Any]]) -> None:
    mode = cfg.handoff_mode
    if mode == "telegram":
        await tg.send_to_handoff_group(tg.format_daily_summary_whatsapp(opps))
    elif mode == "whatsapp_twilio":
        await twilio.send_text_all(tg.format_daily_summary_whatsapp(opps))
    elif mode == "whatsapp_cloud":
        # El resumen es texto multilínea: por Cloud API solo entra como texto libre,
        # que requiere ventana de 24h. Se intenta best-effort.
        await wa.send_text_all(tg.format_daily_summary_whatsapp(opps))
