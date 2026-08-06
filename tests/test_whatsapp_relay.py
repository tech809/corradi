"""Bot dedicado de reenvío a WhatsApp (app/publisher/whatsapp_relay.py)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from telegram.error import Forbidden

from app.publisher import whatsapp_relay as relay


def _cfg(**over):
    base = dict(
        whatsapp_relay_bot_token="123:FAKE",
        whatsapp_relay_bot_username="corradi_erasmus_whatsapp_bot",
        whatsapp_relay_chat_ids=[111, 222],
        admin_telegram_ids=[999],  # distinto a chat_ids adrede: si algo cae en admins, se nota
    )
    base.update(over)
    return SimpleNamespace(**base)


class _FakeBot:
    def __init__(self, token):
        self.token = token
        self.sent: list[tuple[int, str]] = []
        self.forbid_for: set[int] = set()

    async def send_message(self, chat_id, text, disable_web_page_preview=True):
        if chat_id in self.forbid_for:
            raise Forbidden("Forbidden: bot can't initiate conversation with a user")
        self.sent.append((chat_id, text))


def test_is_configured_requires_token_and_destino():
    assert relay.is_configured() is False  # cfg real de tests, sin token


def test_no_op_sin_configurar(monkeypatch):
    monkeypatch.setattr(relay, "cfg", _cfg(whatsapp_relay_bot_token=""))
    # No debe intentar importar/instanciar telegram.Bot si no hay token.
    asyncio.run(relay.send_opportunity("texto"))


def test_manda_a_cada_chat_configurado(monkeypatch):
    monkeypatch.setattr(relay, "cfg", _cfg())
    fake = _FakeBot("123:FAKE")
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    asyncio.run(relay.send_opportunity("🇮🇹 *Blue & Green Inclusion*"))

    assert [chat for chat, _ in fake.sent] == [111, 222]
    assert all(text == "🇮🇹 *Blue & Green Inclusion*" for _, text in fake.sent)


def test_funciona_con_chat_id_de_grupo_negativo():
    """Un grupo tiene un único chat_id negativo -- distinto de un DM, pero la misma API
    (`bot.send_message`) sirve para ambos sin distinción de código."""
    cfg_grupo = _cfg(whatsapp_relay_chat_ids=[-1001234567890])
    assert cfg_grupo.whatsapp_relay_chat_ids == [-1001234567890]


def test_sin_chat_ids_propios_cae_en_admin_telegram_ids(monkeypatch):
    """Mientras no se configure un destino propio (persona o grupo), sigue cayendo en
    ADMIN_TELEGRAM_IDS -- mismo comportamiento que al principio, para no dejar de mandar
    nada mientras se monta el destino nuevo."""
    monkeypatch.setattr(relay, "cfg", _cfg(whatsapp_relay_chat_ids=[]))
    fake = _FakeBot("123:FAKE")
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    asyncio.run(relay.send_opportunity("texto"))

    assert [chat for chat, _ in fake.sent] == [999]  # el admin de _cfg(), no los chat_ids


def test_destino_sin_start_no_revienta_a_los_demas(monkeypatch):
    """Si un chat no le ha hablado al bot todavía (falta /start, o el bot no está en el
    grupo), Telegram responde Forbidden -- no debe tumbar el envío a los demás destinos."""
    monkeypatch.setattr(relay, "cfg", _cfg(whatsapp_relay_chat_ids=[111, 222]))
    fake = _FakeBot("123:FAKE")
    fake.forbid_for = {111}
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    asyncio.run(relay.send_opportunity("texto"))

    assert [chat for chat, _ in fake.sent] == [222]


def test_trocea_mensajes_largos_por_linea_completa(monkeypatch):
    monkeypatch.setattr(relay, "cfg", _cfg(whatsapp_relay_chat_ids=[111]))
    fake = _FakeBot("123:FAKE")
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    largo = "\n".join(f"línea {i} " + "x" * 80 for i in range(100))
    asyncio.run(relay.send_opportunity(largo))

    chunks = [text for _, text in fake.sent]
    assert len(chunks) > 1
    assert all(len(c) <= relay._DM_MAX_LEN for c in chunks)
    assert "\n".join(chunks) == largo  # nada se pierde ni se corta a mitad de línea
