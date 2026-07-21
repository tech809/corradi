"""⚠️ APARCADO para el lanzamiento Telegram-only (ver README), sin usar ahora mismo
(HANDOFF_MODE=none). Funcionó en sandbox; se conserva por si se reactiva WhatsApp más adelante.

Adaptador de WhatsApp vía Twilio (BSP).

Twilio expone la API de WhatsApp con su propio endpoint REST:
  POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
  auth básica (SID:AuthToken), From=whatsapp:+..., To=whatsapp:+...

Mensaje business-initiated (lo que hace el bot) requiere una **Content Template** aprobada
(ContentSid HX...) salvo que el destinatario haya escrito en las últimas 24h (entonces vale
texto libre con Body). Por eso:
  - Si TWILIO_CONTENT_SID está puesto → se manda como plantilla (funciona siempre).
  - Si no → se manda texto libre (solo entra dentro de la ventana de 24h / sandbox tras 'join').
"""
from __future__ import annotations

import asyncio
import json
import logging

from app.config import cfg
from app.publisher import telegram_publisher as tg
from app.publisher.whatsapp_cloud import _template_params

log = logging.getLogger("corradi.twilio")


def is_configured() -> bool:
    return bool(
        cfg.twilio_account_sid and cfg.twilio_auth_token
        and cfg.twilio_whatsapp_from and cfg.whatsapp_recipients
    )


def _url() -> str:
    return f"https://api.twilio.com/2010-04-01/Accounts/{cfg.twilio_account_sid}/Messages.json"


def _to(digits: str) -> str:
    return f"whatsapp:+{digits}"


async def _post(data: dict) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(_url(), data=data, auth=(cfg.twilio_account_sid, cfg.twilio_auth_token))
        if r.status_code >= 400:
            log.error("Twilio %s: %s", r.status_code, r.text)
        r.raise_for_status()
        return r.json()


async def send_opportunity(opp) -> bool:
    if not is_configured():
        log.warning("Twilio no configurado (sid/token/from/recipients) — handoff omitido.")
        return False
    use_template = cfg.twilio_content_sid.strip().upper().startswith("HX")
    ok = True
    for num in cfg.whatsapp_recipients:
        data = {"From": cfg.twilio_whatsapp_from, "To": _to(num)}
        if use_template:
            params = _template_params(opp)
            data["ContentSid"] = cfg.twilio_content_sid.strip()
            data["ContentVariables"] = json.dumps({str(i + 1): v for i, v in enumerate(params)})
        else:
            data["Body"] = tg.format_opportunity_whatsapp(opp)
        try:
            res = await _post(data)
            log.info("Handoff Twilio enviado a %s (%s) sid=%s", num, opp.get("identifier"), res.get("sid"))
        except Exception as e:  # noqa: BLE001
            ok = False
            log.error("Fallo Twilio a %s: %s", num, e)
    return ok


async def send_text(digits: str, body: str) -> dict:
    """Texto libre (solo dentro de ventana 24h / sandbox tras 'join')."""
    data = {"From": cfg.twilio_whatsapp_from, "To": _to("".join(c for c in digits if c.isdigit())), "Body": body}
    return await _post(data)


async def send_text_all(body: str) -> None:
    if not is_configured():
        return
    for num in cfg.whatsapp_recipients:
        try:
            await send_text(num, body)
        except Exception as e:  # noqa: BLE001
            log.warning("Twilio texto a %s falló (¿fuera de ventana 24h?): %s", num, e)


# CLI: python -m app.publisher.whatsapp_twilio text <numero> "<mensaje>"
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) >= 3 and sys.argv[1] == "text":
        number = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else "Prueba CORRADI-BOT ✅"
        print(asyncio.run(send_text(number, message)))
    else:
        print('Uso: python -m app.publisher.whatsapp_twilio text <numero> "<mensaje>"')
