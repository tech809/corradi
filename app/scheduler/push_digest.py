"""Resumen diario push de la app móvil: «Hay N proyectos nuevos para ti».

Cron diario a las 19:30 (hora de Madrid, ver README). Coge las oportunidades abiertas y
visibles en el mapa público (mismo criterio que /api/map: `repo.list_open`) creadas desde el
último resumen —la primera vez, las de las últimas 24 h— y manda una notificación a cada
dispositivo con `daily_digest` activo, filtrando por sus tipos (vacío = todos). Si a un
dispositivo no le toca nada, no se le manda nada; si no hay nada nuevo, no sale ningún push.
`data.ids` lleva los identificadores que cuenta la notificación de ese dispositivo (tras su
filtro de tipos, máx. 50), para que la app enseñe exactamente lo anunciado.

Envío por la Expo Push API (https://docs.expo.dev/push-notifications/sending-notifications/):
lotes de ≤100 mensajes; cada mensaje devuelve un «ticket» en el mismo orden. Los tickets con
`DeviceNotRegistered` borran el token (la app se desinstaló o se quitaron los permisos); el
resto de errores solo se registran en el log.

Recibos: casi todos los DeviceNotRegistered llegan después, en el recibo (getReceipts, ~15 min
tras el envío; Expo los guarda 24 h). Cada ticket aceptado se apunta en `push_tickets`
(0027_push_tickets.sql). `--receipts-only` (cron propio, unos 20 min después del resumen, ver
README) y el arranque de cada resumen consultan los recibos de tickets con más de 15 min en
lotes de ≤1000, borran los tokens con DeviceNotRegistered, registran el resto de errores,
borran los tickets procesados y purgan los de más de 48 h.

Probar a mano:  python -m app.scheduler.push_digest --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app import alerts
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool

log = logging.getLogger("corradi.push_digest")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
BATCH_SIZE = 100            # máximo de mensajes por petición que admite Expo
RECEIPTS_BATCH_SIZE = 1000  # máximo de ids por petición a getReceipts
RECEIPT_DELAY = timedelta(minutes=15)   # Expo recomienda esperar 15 min a los recibos
TICKET_MAX_AGE = timedelta(hours=48)    # los recibos caducan a las 24 h; margen de sobra
FIRST_RUN_WINDOW = timedelta(hours=24)
MAX_IDS = 50                # ids en `data` (~20 bytes cada uno: muy por debajo de los 4 KB)
_TITLE_MAX = 60
_RETRIES = 3                # reintentos ante 429/5xx, con espera exponencial

# Envía un lote de mensajes y devuelve la lista de tickets (mismo orden). Inyectable en tests.
Sender = Callable[[list[dict[str, Any]]], Awaitable[list[dict[str, Any]]]]
# Pide los recibos de unos ticket ids y devuelve {id: recibo} (los que aún no hay, ausentes).
ReceiptFetcher = Callable[[list[str]], Awaitable[dict[str, dict[str, Any]]]]


class ExpoRequestError(RuntimeError):
    """La petición entera falló (4xx/5xx con `errors`, o red): no hay tickets."""


async def _expo_post(url: str, body: Any) -> Any:
    """POST a la Push API con reintentos ante red/429/5xx; devuelve el campo `data`."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/json",
    }
    if cfg.expo_access_token:
        headers["Authorization"] = f"Bearer {cfg.expo_access_token}"
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(_RETRIES + 1):
            try:
                resp = await client.post(url, json=body, headers=headers)
            except httpx.HTTPError as e:
                if attempt == _RETRIES:
                    raise ExpoRequestError(f"{type(e).__name__}: {e}") from e
            else:
                if resp.status_code == 200:
                    return resp.json().get("data")
                # 429 y 5xx se reintentan; un 400 (payload mal formado) no se arregla solo.
                if (resp.status_code != 429 and resp.status_code < 500) or attempt == _RETRIES:
                    raise ExpoRequestError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            await asyncio.sleep(2 ** attempt)
    raise ExpoRequestError("sin respuesta")  # pragma: no cover


async def expo_send(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tickets = await _expo_post(EXPO_PUSH_URL, messages)
    if not isinstance(tickets, list) or len(tickets) != len(messages):
        raise ExpoRequestError(f"Respuesta inesperada de Expo: {str(tickets)[:300]}")
    return tickets


async def expo_get_receipts(ids: list[str]) -> dict[str, dict[str, Any]]:
    receipts = await _expo_post(EXPO_RECEIPTS_URL, {"ids": ids})
    if receipts is None:
        return {}
    if not isinstance(receipts, dict):
        raise ExpoRequestError(f"Respuesta inesperada de Expo: {str(receipts)[:300]}")
    return receipts


# Emoji y pictogramas (incluye ❗, ✨, banderas, selector de variante y unión ZWJ).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\uFE0F\u200D\u20E3]+"
)
_PIPES_RE = re.compile(r"\s*\|+\s*")
_EDGE_SEPARATORS = " ·-–—:,"


def _clean_title(title: str | None) -> str:
    """Título presentable en la notificación: sin emoji ni ❗ y «|» → «·». Las mayúsculas se
    respetan: pasarlas a tipo frase estropeaba siglas y topónimos («en roma», «Tc»)."""
    text = _EMOJI_RE.sub(" ", title or "")
    text = _PIPES_RE.sub(" · ", text)
    text = " ".join(text.split()).strip(_EDGE_SEPARATORS)
    return text or "(sin título)"


def _short(title: str | None) -> str:
    title = _clean_title(title)
    return title if len(title) <= _TITLE_MAX else title[: _TITLE_MAX - 1].rstrip() + "…"


def build_message(token: str, projects: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(projects)
    title = "Hay 1 proyecto nuevo para ti" if n == 1 else f"Hay {n} proyectos nuevos para ti"
    body = " · ".join(_short(p.get("title")) for p in projects[:2])
    if n > 2:
        body += f" y {n - 2} más"
    ids = [p["identifier"] for p in projects if p.get("identifier")][:MAX_IDS]
    return {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
        "data": {"screen": "nuevos", "ids": ids},
        "channelId": "digest",
    }


async def check_receipts(now: datetime | None = None, fetch: ReceiptFetcher | None = None) -> dict[str, int]:
    """Consulta los recibos de los tickets con más de 15 min, da de baja los tokens con
    DeviceNotRegistered y limpia `push_tickets`. Un lote que falla deja sus tickets para la
    siguiente pasada (hasta que caduquen a las 48 h)."""
    fetch = fetch or expo_get_receipts
    now = now or datetime.now(timezone.utc)
    pending = await repo.list_push_tickets_before(now - RECEIPT_DELAY)
    stats = {"tickets": len(pending), "ok": 0, "errors": 0, "removed": 0, "missing": 0, "purged": 0}
    processed: list[str] = []
    dead: list[tuple[str, datetime]] = []
    for i in range(0, len(pending), RECEIPTS_BATCH_SIZE):
        batch = pending[i:i + RECEIPTS_BATCH_SIZE]
        try:
            receipts = await fetch([t["ticket_id"] for t in batch])
        except Exception as e:  # noqa: BLE001
            log.error("Falló la consulta de %s recibos push: %s", len(batch), e)
            continue
        for ticket in batch:
            receipt = receipts.get(ticket["ticket_id"])
            if receipt is None:
                stats["missing"] += 1  # aún no está (o ya caducó): se reintenta hasta las 48 h
                continue
            processed.append(ticket["ticket_id"])
            if receipt.get("status") == "ok":
                stats["ok"] += 1
                continue
            stats["errors"] += 1
            code = (receipt.get("details") or {}).get("error")
            if code == "DeviceNotRegistered":
                dead.append((ticket["token"], ticket["created_at"]))
            else:
                log.warning("Recibo push con error (%s): %s", code, receipt.get("message"))
    if dead:
        stats["removed"] = await repo.delete_push_devices_not_seen_since(dead)
        log.info("Tokens dados de baja por DeviceNotRegistered (recibos): %s", stats["removed"])
    await repo.delete_push_tickets(processed)
    stats["purged"] = await repo.purge_push_tickets(now - TICKET_MAX_AGE)
    log.info("Recibos push: %s", stats)
    return stats


def _new_projects(rows: list[dict[str, Any]], since: datetime, until: datetime) -> list[dict[str, Any]]:
    fresh = [r for r in rows if r.get("created") and since < r["created"] <= until]
    # Lo más reciente primero: son los títulos que se ven en la notificación.
    return sorted(fresh, key=lambda r: r["created"], reverse=True)


async def digest(
    now: datetime | None = None, send: Sender | None = None, dry_run: bool = False,
    fetch_receipts: ReceiptFetcher | None = None,
) -> dict[str, int]:
    """Lógica del resumen (sin abrir/cerrar el pool, para poder probarla con el repo simulado)."""
    send = send or expo_send
    now = now or datetime.now(timezone.utc)
    if not dry_run:
        # Primero los recibos pendientes: así no se manda a tokens que ya se sabe que están muertos.
        # Si falla, se registra y el resumen sigue.
        try:
            await check_receipts(now, fetch_receipts)
        except Exception:  # noqa: BLE001
            log.exception("Falló la consulta de recibos push antes del resumen")
    since = await repo.last_push_digest_at() or now - FIRST_RUN_WINDOW
    projects = _new_projects(await repo.list_open(), since, now)
    stats = {"projects": len(projects), "devices": 0, "sent": 0, "errors": 0, "removed": 0}
    if not projects:
        log.info("Nada nuevo desde %s: no se manda ningún push.", since.isoformat())
        if not dry_run:
            await repo.record_push_digest_run(now, 0, 0)
        return stats

    messages = []
    for device in await repo.list_push_digest_devices():
        wanted = set(device.get("types") or ())
        mine = [p for p in projects if not wanted or p.get("type") in wanted]
        if mine:
            messages.append(build_message(device["token"], mine))
    stats["devices"] = len(messages)
    if dry_run:
        for m in messages[:5]:
            log.info("[dry-run] %s | %s | %s", m["to"][:24], m["title"], m["body"])
        log.info("[dry-run] %s proyectos nuevos, %s dispositivos.", stats["projects"], stats["devices"])
        return stats

    dead: list[str] = []
    accepted: list[tuple[str, str]] = []
    failed_batches = 0
    batches = [messages[i:i + BATCH_SIZE] for i in range(0, len(messages), BATCH_SIZE)]
    for batch in batches:
        try:
            tickets = await send(batch)
        except Exception as e:  # noqa: BLE001
            failed_batches += 1
            log.error("Falló un lote de %s pushes: %s", len(batch), e)
            continue
        for message, ticket in zip(batch, tickets):
            if ticket.get("status") == "ok":
                stats["sent"] += 1
                if ticket.get("id"):
                    accepted.append((ticket["id"], message["to"]))
                continue
            stats["errors"] += 1
            code = (ticket.get("details") or {}).get("error")
            if code == "DeviceNotRegistered":
                dead.append(message["to"])
            else:
                log.warning("Push rechazado (%s): %s", code, ticket.get("message"))
    await repo.save_push_tickets(accepted, now)
    if dead:
        stats["removed"] = await repo.delete_push_devices(dead)
        log.info("Tokens dados de baja por DeviceNotRegistered: %s", stats["removed"])

    if batches and failed_batches == len(batches):
        # Nada llegó a Expo: no se registra la ejecución, así mañana se vuelve a intentar
        # con estos mismos proyectos en vez de perderlos.
        raise ExpoRequestError(f"Fallaron los {failed_batches} lotes de envío")
    if failed_batches:
        await alerts.alert("Resumen push incompleto", f"Fallaron {failed_batches} de {len(batches)} lotes")
    await repo.record_push_digest_run(now, stats["projects"], stats["sent"])
    log.info("Resumen push: %s", stats)
    return stats


async def run(dry_run: bool = False, receipts_only: bool = False) -> None:
    await open_pool()
    try:
        if receipts_only:
            await check_receipts()
        else:
            await digest(dry_run=dry_run)
    except Exception as e:  # noqa: BLE001
        if receipts_only:
            log.exception("Falló la consulta de recibos push")
            await alerts.alert("No se han podido consultar los recibos push de la app", f"{type(e).__name__}: {e}")
        else:
            log.exception("Falló el resumen push diario")
            await alerts.alert("El resumen push de la app no se ha enviado", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="calcula y muestra, sin enviar ni registrar")
    parser.add_argument("--receipts-only", action="store_true",
                        help="solo consulta los recibos pendientes de Expo y da de baja los tokens muertos")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, receipts_only=args.receipts_only))
