"""⚠️ APARCADO para el lanzamiento Telegram-only (ver README), sin usar ahora mismo
(HANDOFF_MODE=none). Se conserva por si se reactiva WhatsApp más adelante.

Adaptador de WhatsApp Business Cloud API (Meta) para el handoff a los admins.

El bot inicia el mensaje (no hay ventana de 24h abierta), así que el envío proactivo DEBE
ir como **plantilla aprobada** (template). Los parámetros de plantilla no admiten saltos de
línea, por eso se mandan campos de una sola línea (la estructura va en la propia plantilla).

Crea en Meta una plantilla (categoría UTILITY) con 5 parámetros de cuerpo {{1}}..{{5}}:
  {{1}} título · {{2}} info (tipo · lugar · fechas) · {{3}} deadline · {{4}} formulario · {{5}} id

Ver docs/whatsapp_cloud_setup.md.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import cfg

log = logging.getLogger("corradi.whatsapp")

_TYPE_LABEL = {
    "YOUTH_EXCHANGE": "Intercambio juvenil",
    "TRAINING_COURSE": "Training course",
    "VOLUNTEERING": "Voluntariado",
    "WORKSHOP": "Workshop",
}


def is_configured() -> bool:
    return bool(cfg.whatsapp_cloud_token and cfg.whatsapp_phone_number_id and cfg.whatsapp_recipients)


def _url() -> str:
    return f"https://graph.facebook.com/{cfg.graph_api_version}/{cfg.whatsapp_phone_number_id}/messages"


async def _post(payload: dict) -> dict:
    import httpx

    headers = {"Authorization": f"Bearer {cfg.whatsapp_cloud_token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(_url(), json=payload, headers=headers)
        if r.status_code >= 400:
            log.error("WhatsApp Cloud %s: %s", r.status_code, r.text)
        r.raise_for_status()
        return r.json()


def _template_params(opp: dict[str, Any]) -> list[str]:
    place = " · ".join(p for p in [opp.get("location"), opp.get("country_code")] if p)
    s, e = opp.get("start_date"), opp.get("end_date")
    dates = f"{s} - {e}" if s and e else str(s or e or "fechas por confirmar")
    info = " · ".join(x for x in [_TYPE_LABEL.get(opp.get("type") or ""), place, dates] if x)
    deadline = str(opp.get("application_deadline") or "-")
    if opp.get("deadline_estimated"):
        deadline += " (estimada)"
    return [
        str(opp.get("title") or "(sin título)"),
        info or "-",
        deadline,
        str(opp.get("application_url") or "-"),
        str(opp.get("identifier") or "-"),
    ]


async def send_opportunity(opp: dict[str, Any]) -> bool:
    """Envía la oportunidad como plantilla a todos los destinatarios. False si no está configurado."""
    if not is_configured():
        log.warning("WhatsApp Cloud no configurado (token/phone_id/recipients) — handoff omitido.")
        return False
    params = _template_params(opp)
    components = [{
        "type": "body",
        "parameters": [{"type": "text", "text": p} for p in params],
    }]
    ok = True
    for to in cfg.whatsapp_recipients:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": cfg.whatsapp_template_name,
                "language": {"code": cfg.whatsapp_template_lang},
                "components": components,
            },
        }
        try:
            await _post(payload)
            log.info("Handoff WhatsApp enviado a %s (%s)", to, opp.get("identifier"))
        except Exception as e:  # noqa: BLE001
            ok = False
            log.error("Fallo enviando handoff WhatsApp a %s: %s", to, e)
    return ok


async def send_text(to: str, body: str) -> dict:
    """Mensaje de texto libre. SOLO funciona dentro de la ventana de 24h iniciada por el
    destinatario (sirve para pruebas si el admin ha escrito antes al número del bot)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": "".join(c for c in to if c.isdigit()),
        "type": "text",
        "text": {"body": body, "preview_url": True},
    }
    return await _post(payload)


async def send_text_all(body: str) -> None:
    if not is_configured():
        return
    for to in cfg.whatsapp_recipients:
        try:
            await send_text(to, body)
        except Exception as e:  # noqa: BLE001
            log.warning("No pude enviar texto a %s (¿fuera de ventana 24h?): %s", to, e)


# CLI de prueba:  python -m app.publisher.whatsapp_cloud text <numero> "<mensaje>"
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) >= 3 and sys.argv[1] == "text":
        number = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else "Prueba CORRADI-BOT ✅"
        print(asyncio.run(send_text(number, message)))
    else:
        print("Uso: python -m app.publisher.whatsapp_cloud text <numero> \"<mensaje>\"")
