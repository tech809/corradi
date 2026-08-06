"""Despachador del handoff a WhatsApp según HANDOFF_MODE, oportunidad a oportunidad.

- telegram        → DM por el bot dedicado de difusión (@corradi_erasmus_whatsapp_bot,
                     ver app/publisher/whatsapp_relay.py) con el texto listo para copiar y
                     pegar en el canal de difusión. Es el modo real hoy: WhatsApp no tiene
                     API accesible para ese canal (difusión, no negocio).
- whatsapp_cloud  → envía la oportunidad por WhatsApp Business Cloud API (plantilla).
                     Sin usar en producción (requiere aprobación de plantilla de Meta),
                     queda listo por si algún día se activa.
- whatsapp_twilio → igual que arriba, vía Twilio como BSP.
- none            → no hace nada.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import cfg
from app.publisher import telegram_publisher as tg
from app.publisher import whatsapp_cloud as wa
from app.publisher import whatsapp_relay as relay
from app.publisher import whatsapp_twilio as twilio

log = logging.getLogger("corradi.handoff")


async def opportunity(opp: dict[str, Any]) -> None:
    mode = cfg.handoff_mode
    if mode == "telegram":
        await relay.send_opportunity(tg.format_opportunity_whatsapp(opp))
    elif mode == "whatsapp_twilio":
        await twilio.send_opportunity(opp)
    elif mode == "whatsapp_cloud":
        await wa.send_opportunity(opp)
    elif mode != "none":
        log.warning("HANDOFF_MODE desconocido: %s", mode)
