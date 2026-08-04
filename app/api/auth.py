"""Login con Telegram para la web (widget oficial) + sesión propia firmada.

Se usa Telegram y no Google/email a propósito: el widget devuelve el MISMO ID numérico de
Telegram con el que ya está montado todo el pipeline (`submitted_by_id`), así que el límite
diario, el antispam, los bloqueos y los permisos de editar/borrar siguen funcionando tal
cual, sin tabla de usuarios ni segundo espacio de identidad. Además una identidad de
Telegram es un canal: el bot puede escribirle a la persona; un email no da nada de vuelta.

No hay contraseñas ni datos personales guardados: de la sesión solo viven el ID, el nombre
y el @usuario, dentro de una cookie firmada (no cifrada — no lleva nada secreto).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import cfg

SESSION_COOKIE = "corradi_session"
_SESSION_DAYS = 30
# El payload que firma Telegram no caduca solo: sin este tope, uno capturado serviría para
# siempre para suplantar a esa persona.
_LOGIN_MAX_AGE_S = 24 * 3600


def _session_secret() -> bytes:
    """Clave derivada del token del bot: así no hay que gestionar otro secreto en el .env,
    y si algún día se rota el token, todas las sesiones caducan solas (que es lo deseable)."""
    return hashlib.sha256(b"corradi-web-session:" + cfg.telegram_bot_token.encode()).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def verify_telegram_login(data: dict[str, str]) -> dict | None:
    """Valida la firma del widget de Telegram con el algoritmo oficial: HMAC-SHA256 sobre
    los campos ordenados `clave=valor`, usando SHA256(token_del_bot) como clave. Devuelve
    {id, name, username} si todo cuadra, o None si la firma no vale o el payload es viejo.
    """
    received = data.get("hash")
    if not received or not cfg.telegram_bot_token:
        return None

    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data) if k != "hash")
    secret = hashlib.sha256(cfg.telegram_bot_token.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None

    try:
        if time.time() - int(data.get("auth_date", 0)) > _LOGIN_MAX_AGE_S:
            return None
        user_id = int(data["id"])
    except (KeyError, TypeError, ValueError):
        return None

    name = " ".join(x for x in (data.get("first_name"), data.get("last_name")) if x).strip()
    return {"id": user_id, "name": name or f"Usuario {user_id}", "username": data.get("username") or None}


def make_session(user: dict) -> str:
    """Cookie de sesión: `payload.firma`, ambos en base64url. Firmada, no cifrada."""
    payload = {
        "id": user["id"], "name": user["name"], "username": user.get("username"),
        "exp": int(time.time()) + _SESSION_DAYS * 86400,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_session_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def read_session(cookie: str | None) -> dict | None:
    """Devuelve el usuario de una cookie válida y no caducada, o None."""
    if not cookie or "." not in cookie:
        return None
    body, _, signature = cookie.partition(".")
    expected = _b64(hmac.new(_session_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
        return None
    return payload


def session_max_age() -> int:
    return _SESSION_DAYS * 86400
