"""Bot dedicado de Telegram (@corradi_erasmus_whatsapp_bot, token propio) que reenvía cada
oportunidad publicada — venga de donde venga: bot de Telegram, panel web, SALTO-YOUTH — a
quien esté configurado como destino, en formato WhatsApp listo para copiar y pegar a mano
en el canal de difusión.

Bot aparte del principal (no el mismo `TELEGRAM_BOT_TOKEN`) para no mezclar tráfico de
moderación con el bot público: este solo sirve para esto.

El destino (`WHATSAPP_RELAY_CHAT_IDS`) puede ser una persona, varias, o un grupo (un grupo
tiene un único chat_id negativo que vale para todos sus miembros a la vez -- más cómodo que
mantener una lista de IDs si quien modera va cambiando). Si no se configura, cae en
`ADMIN_TELEGRAM_IDS` (mismo comportamiento que al principio, para no dejarlo sin mandar
nada mientras se monta un destino propio).

Requisito de la propia API de Telegram: un bot no puede escribir primero en un chat (DM o
grupo) donde nadie le ha hablado antes -- hace falta un /start (DM) o que se le añada y
alguien escriba en el grupo. Si no, `send_message` responde `Forbidden` y aquí se registra
un aviso en vez de reventar (no hay canal alternativo para avisar: es justo este bot el que
estaría averiado)."""
from __future__ import annotations

import logging

from app.config import cfg

log = logging.getLogger("corradi.whatsapp_relay")

# Mismo margen de seguridad que `send_chunked_dm` en telegram_publisher.py, bajo el límite
# real de Telegram (4096) — el texto de una oportunidad es compacto y no debería acercarse
# ni de lejos, pero una `summary` larga podría.
_DM_MAX_LEN = 3900


def _recipients() -> list[int]:
    return cfg.whatsapp_relay_chat_ids or cfg.admin_telegram_ids


def is_configured() -> bool:
    return bool(cfg.whatsapp_relay_bot_token and _recipients())


async def send_opportunity(whatsapp_text: str) -> None:
    """Manda a cada chat configurado el texto ya listo para copiar y pegar en el canal de
    difusión de WhatsApp. Sin foto/banner a propósito: el canal de difusión de WhatsApp es
    solo texto."""
    if not is_configured():
        return
    from telegram import Bot
    from telegram.error import Forbidden

    bot = Bot(cfg.whatsapp_relay_bot_token)
    for chat_id in _recipients():
        try:
            await _send_chunked(bot, chat_id, whatsapp_text)
        except Forbidden:
            log.warning(
                "El chat %s no ha hablado con @%s todavía (falta /start, o añadir el bot "
                "al grupo y escribir algo ahí) -- no he podido reenviarle la oportunidad.",
                chat_id, cfg.whatsapp_relay_bot_username,
            )
        except Exception:  # noqa: BLE001
            log.exception("No pude reenviar la oportunidad al chat %s por el bot de difusión", chat_id)


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
