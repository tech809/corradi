"""Pipeline de ingesta compartido por todos los canales (Telegram, WhatsApp, ...).

Clasifica → extrae → deduplica → guarda → publica (canal Telegram) → handoff (WhatsApp).
Devuelve un dict de estado, agnóstico del canal; cada canal formatea su propia respuesta.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app import geo
from app.config import cfg
from app.db import repository as repo
from app.domain.project import make_hash
from app.llm import embeddings, extractor
from app.publisher import handoff
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.pipeline")


def today_start() -> datetime:
    return datetime.now(ZoneInfo(cfg.timezone)).replace(hour=0, minute=0, second=0, microsecond=0)


def today() -> date:
    """Fecha de hoy en la zona horaria del proyecto (no la del servidor)."""
    return datetime.now(ZoneInfo(cfg.timezone)).date()


async def _spam_check(user_id: int) -> dict[str, bool]:
    """Sistema de 2 avisos: al 1er mensaje seguido que no es oportunidad, aviso; al 2º
    consecutivo, bloqueo automático (indefinido, hasta que un admin lo desbloquee a mano)."""
    recent = await repo.recent_statuses(user_id, cfg.spam_block_threshold)
    blocked = len(recent) >= cfg.spam_block_threshold and all(s == "not_opportunity" for s in recent)
    if not blocked:
        return {"warn": len(recent) >= 1, "blocked": False}

    await repo.block_user(user_id, reason="spam_auto")
    log.warning("Usuario %s bloqueado automáticamente: %s mensajes seguidos que no eran oportunidades",
                user_id, cfg.spam_block_threshold)
    for admin_id in cfg.admin_telegram_ids:
        try:
            await pub.notify_admin(
                admin_id,
                f"🚫 Usuario <code>{user_id}</code> bloqueado automáticamente: "
                f"{cfg.spam_block_threshold} mensajes seguidos que no eran oportunidades (spam).",
            )
        except Exception:  # noqa: BLE001
            log.warning("No pude avisar al admin %s del bloqueo automático", admin_id)
    return {"warn": False, "blocked": True}


async def ingest(raw_text: str, source: str, submitted_by: str, submitted_by_id: int) -> dict[str, Any]:
    """Procesa un mensaje crudo. Estados posibles:
    rate_limited | not_opportunity | expired | deadline_too_far | duplicate |
    duplicate_similar | created | created_no_publish | error
    """
    is_admin = submitted_by_id in cfg.admin_telegram_ids

    # 0) Límite diario (por coordinador; los admins no tienen límite)
    if not is_admin:
        try:
            created_today = await repo.count_created_since(submitted_by_id, today_start())
        except Exception as e:  # noqa: BLE001
            log.exception("Error comprobando el límite diario de %s", submitted_by_id)
            return {"status": "error", "error": str(e)}
        if created_today >= cfg.max_daily_opportunities:
            log.info("%s alcanzó el límite diario (%s/%s)", submitted_by_id, created_today, cfg.max_daily_opportunities)
            await repo.log_submission(submitted_by_id, "rate_limited")
            return {"status": "rate_limited", "limit": cfg.max_daily_opportunities}

    # 1) Clasificación + extracción
    ref_day = today()
    try:
        fields = await asyncio.to_thread(extractor.extract, raw_text, ref_day)
    except extractor.LLMNotConfigured:
        return {"status": "error", "error": "LLM no configurado (falta GEMINI_API_KEY)."}
    except Exception as e:  # noqa: BLE001
        log.exception("Error en extracción (usuario %s)", submitted_by_id)
        await repo.log_submission(submitted_by_id, "error")
        return {"status": "error", "error": str(e)}

    if not fields.get("is_opportunity"):
        log.info("Usuario %s: no es una oportunidad (%s)", submitted_by_id, fields.get("reason"))
        await repo.log_submission(submitted_by_id, "not_opportunity")
        spam = {"warn": False, "blocked": False} if is_admin else await _spam_check(submitted_by_id)
        return {"status": "not_opportunity", "reason": fields.get("reason"), **spam}

    # 1bis) Fuera de plazo: si la fecha límite que trae el mensaje ya pasó, no se publica.
    if fields.get("deadline_in_past"):
        deadline = fields.get("stated_deadline")
        log.info("Usuario %s: oportunidad fuera de plazo (deadline %s < %s)",
                 submitted_by_id, deadline, ref_day)
        await repo.log_submission(submitted_by_id, "expired")
        return {
            "status": "expired",
            "deadline": deadline,
            "title": fields.get("title"),
            "today": ref_day,
        }

    # 1ter) Fecha límite demasiado lejana: probable error de año/fecha, se rechaza para
    # que el coordinador la revise en vez de publicar una deadline absurda.
    if fields.get("deadline_too_far"):
        log.info("Usuario %s: deadline demasiado lejana (%s, tope %s meses)",
                 submitted_by_id, fields.get("application_deadline"), cfg.max_deadline_months)
        await repo.log_submission(submitted_by_id, "deadline_too_far")
        return {
            "status": "deadline_too_far",
            "deadline": fields.get("application_deadline"),
            "title": fields.get("title"),
            "max_months": cfg.max_deadline_months,
        }

    # 2) Deduplicación (hash exacto + embedding semántico)
    try:
        existing = await repo.find_by_hash(
            make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date"))
        )
        if existing:
            log.info("Usuario %s: duplicado exacto de %s", submitted_by_id, existing["identifier"])
            await repo.log_submission(submitted_by_id, "duplicate", existing["id"])
            return {"status": "duplicate", "existing": existing}
        vec = await asyncio.to_thread(embeddings.embed, raw_text)
        dup = await repo.find_similar(vec)
    except Exception as e:  # noqa: BLE001
        log.exception("Error en deduplicación (usuario %s)", submitted_by_id)
        await repo.log_submission(submitted_by_id, "error")
        return {"status": "error", "error": str(e)}

    if dup:
        log.info("Usuario %s: muy parecida a %s (%.0f%%)", submitted_by_id, dup["identifier"], dup["similarity"] * 100)
        await repo.log_submission(submitted_by_id, "duplicate_similar", dup["id"])
        return {"status": "duplicate_similar", "dup": dup}

    # 3) Guardar
    fields["source"] = source
    fields["submitted_by"] = submitted_by
    fields["submitted_by_id"] = submitted_by_id
    try:
        opp = await repo.insert_project(fields, vec)
        await repo.log_submission(submitted_by_id, "created", opp["id"])
    except Exception as e:  # noqa: BLE001
        log.exception("Error guardando (usuario %s)", submitted_by_id)
        return {"status": "error", "error": str(e)}

    # 3bis) Coordenadas para el mapa público. Es un extra: si la geocodificación falla,
    # la oportunidad se publica igual (simplemente no sale en el mapa).
    try:
        coords = await asyncio.to_thread(geo.geocode, opp.get("location"), opp.get("country_code"))
        if coords:
            await repo.set_coords(opp["id"], *coords)
            opp["latitude"], opp["longitude"] = coords
    except Exception:  # noqa: BLE001
        log.warning("No pude geocodificar %s (se publica igual)", opp["identifier"], exc_info=True)

    # 4) Publicar (canal Telegram) + handoff (WhatsApp)
    try:
        message_id = await pub.publish_to_channel(pub.format_opportunity(opp))
        if message_id:
            await repo.mark_published(opp["id"], message_id)
        await handoff.opportunity(opp)
    except Exception as e:  # noqa: BLE001
        log.exception("Error publicando/handoff (%s)", opp["identifier"])
        return {"status": "created_no_publish", "opp": opp, "error": str(e)}

    log.info("Usuario %s: creada y publicada %s", submitted_by_id, opp["identifier"])
    return {"status": "created", "opp": opp, "published": message_id is not None}
