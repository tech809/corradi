"""⚠️ APARCADO para el lanzamiento Telegram-only (ver README). Se deja montado y funcional
por si se reactiva WhatsApp más adelante, pero no forma parte del flujo actual.

Webhook entrante de WhatsApp vía Twilio.

Twilio hace POST aquí cuando un usuario manda un WhatsApp al número del bot. Si el remitente
está autorizado, el mensaje pasa por el MISMO pipeline que Telegram y se responde por WhatsApp.

Configura la URL en Twilio (Sandbox o tu Sender) → "When a message comes in":
    https://<tu-dominio-o-ngrok>/webhooks/twilio   (POST)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response

from app import pipeline
from app.config import cfg
from app.publisher import telegram_publisher as pub
from app.publisher import whatsapp_twilio as tw

router = APIRouter()
log = logging.getLogger("corradi.webhook")


def _digits(value: str | None) -> str:
    return "".join(c for c in (value or "") if c.isdigit())


def _is_allowed(digits: str) -> bool:
    senders = cfg.whatsapp_allowed_senders or cfg.whatsapp_recipients
    return digits in senders


def _valid_signature(url: str, params: dict[str, str], signature: str) -> bool:
    base = url + "".join(k + params[k] for k in sorted(params))
    mac = hmac.new(cfg.twilio_auth_token.encode(), base.encode("utf-8"), hashlib.sha1)
    expected = base64.b64encode(mac.digest()).decode()
    return hmac.compare_digest(expected, signature or "")


def _reply_text(result: dict) -> str:
    s = result["status"]
    if s in ("created", "created_no_publish"):
        opp = result["opp"]
        head = "✅ Guardada"
        if s == "created" and result.get("published"):
            head += " y publicada en el canal de Telegram"
        return f"{head} ({opp['identifier']}).\n\n" + pub.format_opportunity_whatsapp(opp)
    if s == "duplicate":
        ex = result["existing"]
        return f"♻️ Ya existe ({ex['identifier']}): «{ex['title']}». No la republico."
    if s == "duplicate_similar":
        d = result["dup"]
        return f"♻️ Muy parecida ({d['similarity']:.0%}) a «{d['title']}». No la republico."
    if s == "not_opportunity":
        return f"🤔 No parece una oportunidad. {result.get('reason') or ''}".strip()
    return f"⚠️ {result.get('error') or 'Error procesando el mensaje.'}"


async def _process(from_field: str, body: str) -> None:
    digits = _digits(from_field)
    if not _is_allowed(digits):
        await tw.send_text(digits, "🚫 Tu número no está autorizado para enviar oportunidades. "
                                   "Contacta con un administrador.")
        return
    result = await pipeline.ingest(body, source="whatsapp", submitted_by=from_field)
    try:
        await tw.send_text(digits, _reply_text(result))
    except Exception as e:  # noqa: BLE001
        log.error("No pude responder por WhatsApp a %s: %s", digits, e)


@router.post("/webhooks/twilio")
async def inbound(request: Request, background: BackgroundTasks) -> Response:
    form = dict(await request.form())

    if cfg.twilio_validate_signature:
        sig = request.headers.get("X-Twilio-Signature", "")
        if not _valid_signature(str(request.url), form, sig):
            log.warning("Firma de Twilio inválida desde %s", request.client)
            return Response(status_code=403)

    from_field = form.get("From", "")
    body = (form.get("Body") or "").strip()
    if body:
        # Respondemos rápido (200) y procesamos en segundo plano para no agotar el timeout de Twilio.
        background.add_task(_process, from_field, body)
    return Response(content="<Response></Response>", media_type="application/xml")
