"""Login con Telegram + cookie de sesión (app/api/auth.py).

Es el único punto de ESCRITURA pública del sistema: si la verificación de firma se rompe,
cualquiera podría publicar en el canal haciéndose pasar por otra persona. De ahí que se
prueben también los casos que TIENEN que fallar, no solo el que funciona.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from types import SimpleNamespace

import pytest

from app.api import auth

TOKEN = "123456:FAKE-TOKEN-DE-PRUEBA"


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    # `cfg` es un dataclass frozen: no se le puede tocar un atributo, se sustituye entero.
    monkeypatch.setattr(auth, "cfg", SimpleNamespace(telegram_bot_token=TOKEN))


def _firmar(data: dict) -> dict:
    """Reproduce lo que hace Telegram: HMAC-SHA256 de los campos ordenados."""
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(TOKEN.encode()).digest()
    return {**data, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()}


def _payload(**extra):
    return _firmar({
        "id": "6908780215", "first_name": "Jero", "username": "jerxmo",
        "auth_date": str(int(time.time())), **extra,
    })


def test_acepta_una_firma_valida():
    user = auth.verify_telegram_login(_payload())
    assert user == {"id": 6908780215, "name": "Jero", "username": "jerxmo"}


def test_junta_nombre_y_apellido():
    assert auth.verify_telegram_login(_payload(last_name="MS"))["name"] == "Jero MS"


def test_sin_username_publico_no_falla():
    data = _firmar({"id": "1", "first_name": "Ana", "auth_date": str(int(time.time()))})
    assert auth.verify_telegram_login(data)["username"] is None


def test_rechaza_si_manipulan_un_campo():
    """El caso que importa: cambiar el ID después de firmar para suplantar a otra persona."""
    data = _payload()
    data["id"] = "999"
    assert auth.verify_telegram_login(data) is None


def test_rechaza_sin_hash():
    data = _payload()
    del data["hash"]
    assert auth.verify_telegram_login(data) is None


def test_rechaza_un_payload_viejo():
    """Un payload capturado no puede servir para siempre."""
    viejo = str(int(time.time()) - 48 * 3600)
    assert auth.verify_telegram_login(_payload(auth_date=viejo)) is None


def test_rechaza_firma_de_otro_bot(monkeypatch):
    data = _payload()
    monkeypatch.setattr(auth, "cfg", SimpleNamespace(telegram_bot_token="999:OTRO-TOKEN"))
    assert auth.verify_telegram_login(data) is None


def test_sesion_ida_y_vuelta():
    user = {"id": 42, "name": "Ana", "username": "ana"}
    leido = auth.read_session(auth.make_session(user))
    assert (leido["id"], leido["name"], leido["username"]) == (42, "Ana", "ana")


def test_sesion_rechaza_cookie_manipulada():
    cookie = auth.make_session({"id": 42, "name": "Ana", "username": "ana"})
    body, _, firma = cookie.partition(".")
    otra = auth.make_session({"id": 99, "name": "Otro", "username": "otro"}).partition(".")[0]
    # Cuerpo de otra sesión con la firma de la primera: no debe colar.
    assert auth.read_session(f"{otra}.{firma}") is None
    assert auth.read_session(f"{body}.{firma[:-2]}xx") is None


def test_sesion_caducada(monkeypatch):
    cookie = auth.make_session({"id": 42, "name": "Ana", "username": "ana"})
    # El "ahora" se captura ANTES de parchear: si no, la lambda se llamaría a sí misma.
    futuro = time.time() + 400 * 86400
    monkeypatch.setattr(auth.time, "time", lambda: futuro)
    assert auth.read_session(cookie) is None


@pytest.mark.parametrize("cookie", [None, "", "sin-punto", "a.b", "...."])
def test_sesion_basura_no_revienta(cookie):
    assert auth.read_session(cookie) is None
