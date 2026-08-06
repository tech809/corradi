"""Bot dedicado de Telegram (@corradi_erasmus_whatsapp_bot, token propio) que reenvía cada
oportunidad publicada — venga de donde venga: bot de Telegram, panel web, SALTO-YOUTH — al
admin por DM, en formato WhatsApp listo para copiar y pegar a mano en el canal de difusión.

Bot aparte del principal (no el mismo `TELEGRAM_BOT_TOKEN`) para no mezclar tráfico de
moderación con el bot público: este solo sirve para esto, así que su historial de chat con
el admin es limpio y solo tiene lo que hay que copiar.

Requisito de la propia API de Telegram: un bot no puede escribir primero a nadie que no le
haya mandado /start antes. Si un admin no lo ha hecho, `send_message` responde `Forbidden`
y aquí se registra un aviso en vez de reventar (no hay canal alternativo para avisarle: es
justo este bot el que estaría averiado).
"""
from __future__ import annotations

import logging

from app.config import cfg

log = logging.getLogger("corradi.whatsapp_relay")

# Mismo margen de seguridad que `send_chunked_dm` en telegram_publisher.py, bajo el límite
# real de Telegram (4096) — el texto de una oportunidad es compacto y no debería acercarse
# ni de lejos, pero una `summary` larga podría.
_DM_MAX_LEN = 3900


def is_configured() -> bool:
    return bool(cfg.whatsapp_relay_bot_token and cfg.admin_telegram_ids)


async def send_opportunity(whatsapp_text: str) -> None:
    """DM a cada admin con el texto ya listo para copiar y pegar en el canal de difusión de
    WhatsApp. Sin foto/banner a propósito: el canal de difusión de WhatsApp es solo texto."""
    if not is_configured():
        return
    from telegram import Bot
    from telegram.error import Forbidden

    bot = Bot(cfg.whatsapp_relay_bot_token)
    for admin_id in cfg.admin_telegram_ids:
        try:
            await _send_chunked(bot, admin_id, whatsapp_text)
        except Forbidden:
            log.warning(
                "El admin %s no ha iniciado conversación con @%s todavía (mándale /start) "
                "-- no he podido reenviarle la oportunidad.",
                admin_id, cfg.whatsapp_relay_bot_username,
            )
        except Exception:  # noqa: BLE001
            log.exception("No pude reenviar la oportunidad al admin %s por el bot de difusión", admin_id)


async def _send_chunked(bot, chat_id: int, text: str) -> None:
    """Trocea por saltos de línea completos si hace falta (nunca a mitad de línea) — mismo
    criterio que `send_chunked_dm` en telegram_publisher.py."""
    if len(text) <= _DM_MAX_LEN:
        await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
        return
    chunk = ""
    for line in text.split("\n"):
        candidate = f"{chunk}\n{line}" if chunk else line
        if len(candidate) > _DM_MAX_LEN:
            if chunk:
                await bot.send_message(chat_id=chat_id, text=chunk, disable_web_page_preview=True)
            chunk = line
        else:
            chunk = candidate
    if chunk:
        await bot.send_message(chat_id=chat_id, text=chunk, disable_web_page_preview=True)
