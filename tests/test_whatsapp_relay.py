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
        admin_telegram_ids=[111, 222],
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


def test_is_configured_requires_token_and_admins():
    assert relay.is_configured() is False  # cfg real de tests, sin token


def test_no_op_sin_configurar(monkeypatch):
    monkeypatch.setattr(relay, "cfg", _cfg(whatsapp_relay_bot_token=""))
    # No debe intentar importar/instanciar telegram.Bot si no hay token.
    asyncio.run(relay.send_opportunity("texto"))


def test_manda_dm_a_cada_admin(monkeypatch):
    monkeypatch.setattr(relay, "cfg", _cfg())
    fake = _FakeBot("123:FAKE")
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    asyncio.run(relay.send_opportunity("🇮🇹 *Blue & Green Inclusion*"))

    assert [chat for chat, _ in fake.sent] == [111, 222]
    assert all(text == "🇮🇹 *Blue & Green Inclusion*" for _, text in fake.sent)


def test_admin_sin_start_no_revienta_a_los_demas(monkeypatch, caplog):
    """Si un admin no le ha mandado /start al bot todavía, Telegram responde Forbidden --
    no debe tumbar el envío a los demás admins configurados."""
    monkeypatch.setattr(relay, "cfg", _cfg(admin_telegram_ids=[111, 222]))
    fake = _FakeBot("123:FAKE")
    fake.forbid_for = {111}
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    asyncio.run(relay.send_opportunity("texto"))

    assert [chat for chat, _ in fake.sent] == [222]


def test_trocea_mensajes_largos_por_linea_completa(monkeypatch):
    monkeypatch.setattr(relay, "cfg", _cfg(admin_telegram_ids=[111]))
    fake = _FakeBot("123:FAKE")
    monkeypatch.setattr("telegram.Bot", lambda token: fake)

    largo = "\n".join(f"línea {i} " + "x" * 80 for i in range(100))
    asyncio.run(relay.send_opportunity(largo))

    chunks = [text for _, text in fake.sent]
    assert len(chunks) > 1
    assert all(len(c) <= relay._DM_MAX_LEN for c in chunks)
    assert "\n".join(chunks) == largo  # nada se pierde ni se corta a mitad de línea
