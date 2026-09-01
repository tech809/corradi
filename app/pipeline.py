"""Pipeline de ingesta compartido por todos los canales (Telegram, WhatsApp, ...).

Clasifica → extrae → deduplica → guarda → publica (canal Telegram) → handoff (WhatsApp).
Devuelve un dict de estado, agnóstico del canal; cada canal formatea su propia respuesta.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app import geo, images
from app.config import cfg
from app.db import repository as repo
from app.domain.project import canonicalize_organiser, make_hash
from app.llm import embeddings, extractor
from app.publisher import handoff
from app.publisher import instagram
from app.publisher import card_v2
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.pipeline")


def today_start() -> datetime:
    return datetime.now(ZoneInfo(cfg.timezone)).replace(hour=0, minute=0, second=0, microsecond=0)


def today() -> date:
    """Fecha de hoy en la zona horaria del proyecto (no la del servidor)."""
    return datetime.now(ZoneInfo(cfg.timezone)).date()


async def _spam_check(user_id: int, username: str | None = None) -> dict[str, bool]:
    """Sistema de 2 avisos: al 1er mensaje seguido que no es oportunidad, aviso; al 2º
    consecutivo, bloqueo automático (indefinido, hasta que un admin lo desbloquee a mano)."""
    recent = await repo.recent_statuses(user_id, cfg.spam_block_threshold)
    blocked = len(recent) >= cfg.spam_block_threshold and all(s == "not_opportunity" for s in recent)
    if not blocked:
        return {"warn": len(recent) >= 1, "blocked": False}

    await repo.block_user(user_id, reason="spam_auto")
    log.warning("Usuario %s (@%s) bloqueado automáticamente: %s mensajes seguidos que no eran oportunidades",
                user_id, username, cfg.spam_block_threshold)
    # @username si lo tiene (no todo el mundo lo tiene público) + un enlace tg://user que
    # SIEMPRE funciona (abre el chat directo desde el ID, con o sin @) -- para no depender
    # de que el admin tenga que ir a buscar al usuario a mano por el ID numérico solo.
    quien = f"@{username} (<code>{user_id}</code>)" if username else f"<code>{user_id}</code>"
    for admin_id in cfg.admin_telegram_ids:
        try:
            await pub.notify_admin(
                admin_id,
                f"🚫 Usuario {quien} bloqueado automáticamente: "
                f"{cfg.spam_block_threshold} mensajes seguidos que no eran oportunidades (spam).\n"
                f'<a href="tg://user?id={user_id}">Hablar con él/ella →</a>',
            )
        except Exception:  # noqa: BLE001
            log.warning("No pude avisar al admin %s del bloqueo automático", admin_id)
    return {"warn": False, "blocked": True}


async def preview(
    raw_text: str, submitted_by_id: int, *,
    corrections: list[str] | None = None, submitted_by_username: str | None = None,
) -> dict[str, Any]:
    """Fase A: clasifica, extrae (con correcciones opcionales), comprueba plazo y
    duplicados — pero NO guarda ni publica. Para el flujo de confirmación del coordinador.

    Estados: rate_limited | not_opportunity | expired | deadline_too_far | duplicate |
    duplicate_similar | error | ready. En 'ready' devuelve `fields` (sin guardar).
    """
    is_admin = submitted_by_id in cfg.admin_telegram_ids

    # 0) Límite diario (cuenta las PUBLICADAS; las previews no gastan cupo).
    if not is_admin:
        try:
            created_today = await repo.count_created_since(submitted_by_id, today_start())
        except Exception as e:  # noqa: BLE001
            log.exception("Error comprobando el límite diario de %s", submitted_by_id)
            return {"status": "error", "error": str(e)}
        if created_today >= cfg.max_daily_opportunities:
            log.info("%s alcanzó el límite diario (%s/%s)", submitted_by_id, created_today, cfg.max_daily_opportunities)
            await repo.log_submission(submitted_by_id, "rate_limited", raw_text=raw_text)
            return {"status": "rate_limited", "limit": cfg.max_daily_opportunities}

    # 1) Clasificación + extracción
    ref_day = today()
    try:
        fields = await asyncio.to_thread(extractor.extract, raw_text, ref_day, corrections)
    except extractor.LLMNotConfigured:
        return {"status": "error", "error": "LLM no configurado (falta GEMINI_API_KEY)."}
    except json.JSONDecodeError:
        # El texto crudo del parser ("Invalid control character at: line 14 column...") no
        # significa nada para quien envía la oportunidad -- se registra completo para
        # depurar, pero al usuario se le pide simplemente reintentarlo.
        log.exception("Gemini devolvió JSON inválido (usuario %s)", submitted_by_id)
        await repo.log_submission(submitted_by_id, "error", raw_text=raw_text, reason="JSON inválido de Gemini")
        return {"status": "error", "error": "No he podido interpretar la respuesta del extractor. Reenvía el mensaje, prueba a reintentarlo."}
    except Exception as e:  # noqa: BLE001
        log.exception("Error en extracción (usuario %s)", submitted_by_id)
        await repo.log_submission(submitted_by_id, "error", raw_text=raw_text, reason=str(e))
        return {"status": "error", "error": str(e)}
    finally:
        # Se vacía pase lo que pase (incluso si luego se lanzó una excepción): la llamada a
        # Gemini ya se pagó, así que el gasto se registra siempre, no solo cuando todo sale bien.
        await extractor.flush_usage()

    if not fields.get("is_opportunity"):
        log.info("Usuario %s: no es una oportunidad (%s)", submitted_by_id, fields.get("reason"))
        await repo.log_submission(submitted_by_id, "not_opportunity", raw_text=raw_text, reason=fields.get("reason"))
        spam = {"warn": False, "blocked": False} if is_admin else await _spam_check(submitted_by_id, submitted_by_username)
        return {"status": "not_opportunity", "reason": fields.get("reason"), **spam}

    # Un infopack legible aporta la descripción extensa y los detalles prácticos. Es un
    # enriquecimiento opcional: si el alojamiento del documento bloquea bots, seguimos con
    # lo que ya se extrajo del anuncio.
    if fields.get("infopack_url"):
        fields = await asyncio.to_thread(extractor.enrich_from_infopack, fields)
        await extractor.flush_usage()

    # 1bis) Fuera de plazo: la fecha límite que trae el mensaje ya pasó.
    if fields.get("deadline_in_past"):
        deadline = fields.get("stated_deadline")
        log.info("Usuario %s: oportunidad fuera de plazo (deadline %s < %s)",
                 submitted_by_id, deadline, ref_day)
        await repo.log_submission(submitted_by_id, "expired", raw_text=raw_text)
        return {"status": "expired", "deadline": deadline, "title": fields.get("title"), "today": ref_day}

    # 1ter) Fecha límite demasiado lejana: probable error de año/fecha.
    if fields.get("deadline_too_far"):
        log.info("Usuario %s: deadline demasiado lejana (%s, tope %s meses)",
                 submitted_by_id, fields.get("application_deadline"), cfg.max_deadline_months)
        await repo.log_submission(submitted_by_id, "deadline_too_far", raw_text=raw_text)
        return {
            "status": "deadline_too_far", "deadline": fields.get("application_deadline"),
            "title": fields.get("title"), "max_months": cfg.max_deadline_months,
        }

    # 1quater) Sin lugar físico: CORRADI-BOT es sobre movilidad presencial, no se publican
    # actividades 100% online (bug real: "ID Talks: Social Sport" se coló vía SALTO).
    if fields.get("is_online"):
        log.info("Usuario %s: '%s' es online (ubicación: %s), no se publica",
                 submitted_by_id, fields.get("title"), fields.get("location"))
        await repo.log_submission(submitted_by_id, "online_not_allowed", raw_text=raw_text)
        return {"status": "online_not_allowed", "title": fields.get("title"), "location": fields.get("location")}

    # 1quinquies) Unificar el nombre de la asociación con uno ya existente en la BD si es
    # (esencialmente) el mismo, para que variantes de acentos/mayúsculas/orden no cuenten
    # como asociaciones distintas en /estadisticas (p.ej. "Tierra Nómada" vs "tierra nomada").
    if fields.get("organiser_name"):
        existing_organisers = await repo.distinct_organiser_names()
        fields["organiser_name"] = canonicalize_organiser(fields["organiser_name"], existing_organisers)

    # Fotografía editorial con atribución; la portada tiene fallback propio si no hay clave.
    fields = await asyncio.to_thread(images.enrich, fields)

    # 2) Deduplicación (hash exacto + embedding semántico)
    try:
        existing = await repo.find_by_hash(
            make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date"))
        )
        if existing:
            log.info("Usuario %s: duplicado exacto de %s", submitted_by_id, existing["identifier"])
            await repo.log_submission(submitted_by_id, "duplicate", existing["id"])
            return {"status": "duplicate", "existing": existing}
        vec = await asyncio.to_thread(embeddings.embed, fields["raw_message"])
        dup = await repo.find_similar(vec)
        if not dup:
            dup = await repo.find_cross_lang_dup(vec, fields.get("country_code"), fields.get("start_date"))
        # Se guarda para que `commit()` NO vuelva a pedir el mismo embedding (misma
        # llamada, mismo texto) — la mitad de peticiones al modelo y menos 429 de cuota.
        fields["_embedding"] = list(vec)
    except Exception as e:  # noqa: BLE001
        log.exception("Error en deduplicación (usuario %s)", submitted_by_id)
        await repo.log_submission(submitted_by_id, "error", raw_text=raw_text, reason=str(e))
        return {"status": "error", "error": str(e)}

    if dup:
        log.info("Usuario %s: muy parecida a %s (%.0f%%)", submitted_by_id, dup["identifier"], dup["similarity"] * 100)
        await repo.log_submission(submitted_by_id, "duplicate_similar", dup["id"])
        return {"status": "duplicate_similar", "dup": dup}

    return {"status": "ready", "fields": fields}


async def _publish_reel_background(opp: dict[str, Any]) -> None:
    """Genera y publica el Reel en segundo plano, sin bloquear `commit()` — ver el
    comentario donde se lanza esta tarea. Un fallo aquí no tiene ningún efecto en el resto
    del pipeline (Telegram y el feed/story de Instagram ya se publicaron)."""
    try:
        await instagram.publish_reel(opp)
    except Exception:  # noqa: BLE001
        log.exception(
            "Reel de Instagram falló para %s (feed/story ya publicados; sin reintento para el Reel)",
            opp["identifier"],
        )


async def _publish_instagram_background(opp: dict[str, Any]) -> None:
    """Encola y publica en Instagram (feed+story, y en cadena el Reel) en segundo plano.

    Antes esto se hacía dentro de `commit()` justo antes de devolver el resultado al bot,
    así que el coordinador se quedaba esperando la respuesta de la Graph API de Instagram
    (varios segundos) para recibir una confirmación de algo que, para entonces, ya estaba
    publicado en el canal de Telegram desde hacía rato. Al moverlo a una tarea de fondo,
    `commit()` devuelve en cuanto Telegram (el canal principal) está publicado, y esta
    función sigue su curso sola — exactamente el mismo patrón que ya usa el Reel, y con la
    misma red de seguridad: `repo.enqueue_instagram` deja la fila en la cola de reintento del
    barrido de cada 2h pase lo que pase aquí, así que un fallo aquí nunca pierde el intento.
    """
    try:
        await repo.enqueue_instagram(opp["id"])
        if instagram.is_configured() and await instagram.gap_ok():
            queue_id = await repo.get_instagram_queue_id(opp["id"])
            if queue_id:
                try:
                    ig_media_id, ig_story_id = await instagram.publish_opportunity(opp)
                    await repo.mark_instagram_published(queue_id, ig_media_id, ig_story_id)
                    await _publish_reel_background(opp)
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "Instagram: fallo publicando %s al instante, queda para el barrido: %s",
                        opp["identifier"], e,
                    )
                    await repo.mark_instagram_failed(queue_id, f"{type(e).__name__}: {e}")
        # Si no ha pasado el espaciado mínimo, se queda 'pending' tal cual — el barrido de
        # cada 2h (o el siguiente commit(), si el hueco ya se abrió) la publicará después.
    except Exception:  # noqa: BLE001
        log.exception("Error encolando/publicando en Instagram (%s)", opp["identifier"])


async def commit(
    fields: dict[str, Any], source: str, submitted_by: str, submitted_by_id: int,
) -> dict[str, Any]:
    """Fase B: guarda, geocodifica y publica una ficha ya validada por el coordinador.
    Estados: created | created_no_publish | error.
    """
    fields = dict(fields)
    fields["source"] = source
    fields["submitted_by"] = submitted_by
    fields["submitted_by_id"] = submitted_by_id
    reused_vec = fields.pop("_embedding", None)   # calculado ya en preview()
    try:
        if reused_vec is not None:
            vec = reused_vec
        else:
            try:
                vec = await asyncio.to_thread(embeddings.embed, fields["raw_message"])
            except Exception:  # noqa: BLE001
                # El vector de commit SOLO se guarda para deduplicar en el futuro; la
                # comprobación de duplicados ya se hizo en preview(). Si falla (típico:
                # cuota 429), se publica sin vector y se rellena luego con
                # `app.scheduler.backfill_embeddings` — no se tumba el post.
                log.warning("Sin embedding para %s; se publica sin vector (backfill luego)",
                            fields.get("title"), exc_info=True)
                vec = None
        opp = await repo.insert_project(fields, vec)
        await repo.log_submission(submitted_by_id, "created", opp["id"])
    except Exception as e:  # noqa: BLE001
        log.exception("Error guardando (usuario %s)", submitted_by_id)
        return {"status": "error", "error": str(e)}

    # Coordenadas para el mapa (extra: si falla, se publica igual sin pin).
    try:
        coords = await asyncio.to_thread(geo.geocode, opp.get("location"), opp.get("country_code"))
        if coords:
            await repo.set_coords(opp["id"], *coords)
            opp["latitude"], opp["longitude"] = coords
    except Exception:  # noqa: BLE001
        log.warning("No pude geocodificar %s (se publica igual)", opp["identifier"], exc_info=True)

    # Publicar (canal Telegram, como foto+pie — bandera/título/categoría van en la imagen,
    # el resto en el pie) + handoff (WhatsApp)
    try:
        caption = pub.format_opportunity(opp, buttons=True, show_title=False, show_type=False)
        image = await asyncio.to_thread(card_v2.render, opp)
        message_id = await pub.publish_photo_to_channel(
            image, caption, reply_markup=pub.opportunity_keyboard(opp)
        )
        if message_id:
            await repo.mark_published(opp["id"], message_id)
        await handoff.opportunity(opp)
    except Exception as e:  # noqa: BLE001
        log.exception("Error publicando/handoff (%s)", opp["identifier"])
        # La cerramos ya mismo: si se queda 'open' pero nunca llegó a publicarse, el propio
        # dedup (que solo mira status='open') bloquearía un reenvío del coordinador con un
        # "ya existe" — dejándolo atascado sin la oportunidad publicada y sin poder
        # reintentarlo. Cerrada, un reenvío genera una ficha nueva sin chocar con esta.
        try:
            await repo.close_project(opp["identifier"])
        except Exception:  # noqa: BLE001
            log.exception("No pude cerrar %s tras el fallo de publicación", opp["identifier"])
        return {"status": "created_no_publish", "opp": opp, "error": str(e)}

    # Instagram (feed+story+Reel) se publica en segundo plano — ver _publish_instagram_background.
    # El coordinador ya tiene su confirmación en cuanto Telegram está publicado; no tiene
    # sentido hacerle esperar la Graph API de Instagram para un "ya está" que, para el canal
    # que de verdad importa, ya era cierto varios segundos antes.
    asyncio.create_task(_publish_instagram_background(opp))

    log.info("Usuario %s: creada y publicada %s", submitted_by_id, opp["identifier"])
    return {"status": "created", "opp": opp, "published": message_id is not None}


async def edit_published(
    identifier: str, instruction: str, editor_id: int,
) -> dict[str, Any]:
    """Reedita una oportunidad YA publicada aplicando una instrucción en lenguaje natural
    ('cámbiale la fecha de fin al 20'). Solo cambia la BD (y por tanto la web/mapa); el
    mensaje de Telegram ya enviado se queda como estaba. Solo el autor o un admin.

    Estados: not_found | forbidden | error | edited.
    """
    opp = await repo.get_by_identifier(identifier)
    if not opp:
        return {"status": "not_found"}
    is_admin = editor_id in cfg.admin_telegram_ids
    if opp.get("submitted_by_id") != editor_id and not is_admin:
        return {"status": "forbidden"}

    ref_day = today()
    try:
        fields = await asyncio.to_thread(
            extractor.extract, opp["raw_message"], ref_day, [instruction]
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Error reeditando %s", identifier)
        return {"status": "error", "error": str(e)}
    finally:
        await extractor.flush_usage()

    if not fields.get("is_opportunity"):
        # Raro: el texto original ya era válido. Se avisa en vez de romper la ficha.
        return {"status": "error", "error": "No pude aplicar el cambio manteniendo una oportunidad válida."}

    if fields.get("organiser_name"):
        existing_organisers = await repo.distinct_organiser_names()
        fields["organiser_name"] = canonicalize_organiser(fields["organiser_name"], existing_organisers)

    try:
        updated = await repo.update_project(identifier, fields)
        # Regeocodificar por si cambió la ubicación.
        coords = await asyncio.to_thread(geo.geocode, updated.get("location"), updated.get("country_code"))
        if coords:
            await repo.set_coords(updated["id"], *coords)
            updated["latitude"], updated["longitude"] = coords
    except Exception as e:  # noqa: BLE001
        log.exception("Error guardando la edición de %s", identifier)
        return {"status": "error", "error": str(e)}

    log.info("Usuario %s editó %s", editor_id, identifier)
    return {"status": "edited", "opp": updated}


async def delete_published(identifier: str, deleter_id: int) -> dict[str, Any]:
    """Cierra (no borra la fila) una oportunidad publicada, a petición de quien la envió
    (o un admin). Desaparece del mapa/lista; el mensaje ya publicado en el canal NO se
    puede retirar, se queda como estaba — mismo criterio que `edit_published`.

    Estados: not_found | forbidden | already_closed | error | deleted.
    """
    opp = await repo.get_by_identifier(identifier)
    if not opp:
        return {"status": "not_found"}
    is_admin = deleter_id in cfg.admin_telegram_ids
    if opp.get("submitted_by_id") != deleter_id and not is_admin:
        return {"status": "forbidden"}
    if opp.get("status") != "open":
        return {"status": "already_closed"}
    try:
        await repo.close_project(identifier)
    except Exception as e:  # noqa: BLE001
        log.exception("Error eliminando %s", identifier)
        return {"status": "error", "error": str(e)}
    log.info("Usuario %s eliminó %s", deleter_id, identifier)
    return {"status": "deleted", "opp": opp}


async def ingest(raw_text: str, source: str, submitted_by: str, submitted_by_id: int) -> dict[str, Any]:
    """Auto-publicar sin confirmación (WhatsApp entrante): preview + commit de una vez.
    El bot de Telegram NO usa esto: usa preview()/commit() con paso de confirmación."""
    p = await preview(raw_text, submitted_by_id)
    if p["status"] != "ready":
        return p
    return await commit(p["fields"], source, submitted_by, submitted_by_id)
