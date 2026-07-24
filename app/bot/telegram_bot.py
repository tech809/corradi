"""Bot de captura de oportunidades en Telegram (acceso abierto + LLM + dedup + publicación)."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

from app import alerts, pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.bot")

_CONTACT = "@pachums97"


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola 👋 Soy el bot de CORRADI-BOT: alimento el canal de difusión de Corradi Erasmus+.\n\n"
        "¿Cómo funciona? Pégame el mensaje de una oportunidad tal cual lo tengas. Te enseño "
        "cómo quedaría publicada y tú decides: <b>Enviar</b>, <b>Modificar</b> algo o "
        "<b>Cancelar</b>. Solo se publica cuando le das a Enviar.\n\n"
        f"⚠️ Manda solo oportunidades reales, una por mensaje (máximo "
        f"{cfg.max_daily_opportunities} al día). Si mandas algo que no es una oportunidad te "
        "aviso; si se repite, se bloquea el acceso automáticamente.\n\n"
        "Usa /ayuda para ver el resto de comandos.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_ayuda(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 <b>Comandos de CORRADI-BOT</b>\n\n"
        "<b>Para publicar una oportunidad:</b> pégame el texto tal cual (con emojis, sin "
        "limpiar nada). Yo extraigo estos campos, asegúrate de que están: título/fechas/"
        "país/deadline/formulario/infopack/contacto.\n\n"
        "Te enseño cómo quedaría. Tú decides: <b>✅ Enviar</b>, <b>✏️ Modificar</b> o "
        "<b>❌ Cancelar</b>.\n\n"
        "📋 <b>Reglas:</b>\n"
        "• Una oportunidad por mensaje (si tienes varias, mándalas por separado)\n"
        f"• Máximo {cfg.max_daily_opportunities} al día\n"
        "• Solo oportunidades reales — si mandas algo que no lo es, te aviso; si se repite, "
        "se bloquea el acceso automáticamente\n\n"
        "📂 <b>/editarmisproyectos</b> — tus oportunidades abiertas: editarlas o eliminarlas\n"
        "📜 <b>/historicomisproyectos</b> — todo lo que has publicado, con su estado\n\n"
        '🌍 Canal de difusión: <a href="https://t.me/erasmuscorradi">t.me/erasmuscorradi</a> · '
        '🗺️ Mapa: <a href="https://mapa.proactivefuture.eu/corradi-erasmus">ver oportunidades</a>\n\n'
        f"¿Dudas o algún error (p.ej. bloqueo injusto)? Contacta con {_CONTACT}.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


def _project_keyboard(identifier: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Editar", callback_data=f"edit:{identifier}"),
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del:{identifier}"),
    ]])


async def cmd_editarmisproyectos(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Backlog editable: las oportunidades del coordinador que siguen ABIERTAS."""
    user = update.effective_user
    rows = await repo.list_open_by_user(user.id)
    if not rows:
        await update.message.reply_text(
            "No tienes ninguna oportunidad publicada y abierta ahora mismo.\n"
            "Cuando publiques alguna, aquí podrás editarla."
        )
        return
    await update.message.reply_text(
        f"📂 <b>Tus oportunidades abiertas ({len(rows)})</b>\n"
        "✏️ Editar cambia el texto (te pregunto qué). 🗑️ Eliminar la retira del mapa y la "
        "lista (te pido confirmación). En ambos casos, lo que ya salió en el canal se queda "
        "como estaba: eso no se puede deshacer.",
        parse_mode=ParseMode.HTML,
    )
    for o in rows:
        await update.message.reply_text(
            pub.format_summary_item(o),
            parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            reply_markup=_project_keyboard(o["identifier"]),
        )


_HISTORY_ICONS = {"open": "🟢 Abierta", "closed": "⚫ Eliminada", "expired": "📅 Caducada"}


async def cmd_historicomisproyectos(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Todo lo que ha publicado el coordinador, cualquier estado (solo lectura)."""
    user = update.effective_user
    rows = await repo.list_all_by_user(user.id)
    if not rows:
        await update.message.reply_text("Todavía no has publicado ninguna oportunidad.")
        return
    lines = [f"📜 <b>Histórico de tus oportunidades ({len(rows)})</b>\n"]
    for o in rows:
        estado = _HISTORY_ICONS.get(o["status"], o["status"])
        lines.append(f"{estado} — <b>{o['title']}</b>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


def _reject_text(result: dict) -> str | None:
    """Mensaje para un estado de rechazo del preview (o None si el estado es 'ready')."""
    status = result["status"]
    if status == "rate_limited":
        return (f"⏳ Ya has mandado {result['limit']} oportunidades hoy, el máximo diario. "
                "Vuelve a intentarlo mañana.")
    if status == "not_opportunity":
        if result.get("blocked"):
            return ("🚫 Se ha bloqueado tu acceso automáticamente por mandar dos mensajes seguidos "
                    f"que no son oportunidades. Si crees que es un error, contacta con {_CONTACT}.")
        text = f"🤔 No parece una oportunidad. Motivo: {result.get('reason') or '—'}"
        if result.get("warn"):
            text += "\n\n⚠️ Aviso: si vuelve a pasar, se bloqueará tu acceso automáticamente."
        return text
    if status == "expired":
        titulo = f"«{result['title']}» " if result.get("title") else ""
        return (f"📅 Esa oportunidad {titulo}está fuera de plazo: la fecha límite de inscripción "
                f"({result.get('deadline')}) ya ha pasado, así que no la publico.\n\n"
                "Si te has confundido de fecha o han ampliado el plazo, corrígela y vuelve a mandármela.")
    if status == "deadline_too_far":
        titulo = f"«{result['title']}» " if result.get("title") else ""
        return (f"📆 La fecha límite que he extraído para {titulo}es {result.get('deadline')}, dentro de "
                f"más de {result.get('max_months')} meses. Probablemente hay un error en la fecha "
                "(año equivocado, etc.) y no la publico.\n\nRevisa el mensaje y vuelve a mandármelo.")
    if status == "duplicate":
        return f"♻️ Ya existe: «{result['existing']['title']}». No la republico."
    if status == "duplicate_similar":
        dup = result["dup"]
        return f"♻️ Muy parecida ({dup['similarity']:.0%}) a «{dup['title']}». No la republico."
    return None


_PREVIEW_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Enviar", callback_data="send"),
    InlineKeyboardButton("✏️ Modificar", callback_data="modify"),
    InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
]])


async def _show_preview(message, ctx: ContextTypes.DEFAULT_TYPE, result: dict) -> None:
    """Guarda la ficha pendiente y muestra la vista previa con los botones."""
    pend = ctx.user_data.get("pending") or {}
    pend["fields"] = result["fields"]
    ctx.user_data["pending"] = pend
    ctx.user_data.pop("awaiting", None)
    await message.reply_text(
        "👀 <b>Así quedaría publicada.</b> Revisa que esté todo bien:\n\n"
        + pub.format_opportunity(result["fields"])
        + "\n\n¿La <b>envío</b> al canal, quieres <b>modificar</b> algo o la <b>cancelas</b>?",
        parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=_PREVIEW_KEYBOARD,
    )


async def on_submission(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await repo.is_blocked(user.id):
        log.info("Mensaje rechazado: %s (@%s) está bloqueado", user.id, user.username)
        await update.message.reply_text(
            f"🚫 Tu acceso está bloqueado. Si crees que es un error, contacta con {_CONTACT}."
        )
        return

    raw = update.message.text
    await update.message.chat.send_action("typing")
    awaiting = ctx.user_data.get("awaiting")

    # a) El coordinador está respondiendo a "¿qué cambio?" de una ficha en preview.
    if awaiting == "modify" and ctx.user_data.get("pending"):
        pend = ctx.user_data["pending"]
        pend.setdefault("corrections", []).append(raw)
        result = await pipeline.preview(pend["raw_text"], user.id, corrections=pend["corrections"])
        if result["status"] == "ready":
            await _show_preview(update.message, ctx, result)
        else:
            # La corrección la deja inválida (fuera de plazo, etc.): se avisa pero se
            # mantiene la ficha anterior por si quiere probar otra corrección.
            pend["corrections"].pop()
            ctx.user_data["awaiting"] = "modify"
            await update.message.reply_text(
                (_reject_text(result) or "No pude aplicar ese cambio.")
                + "\n\n(La ficha anterior sigue en pie: dime otro cambio o pulsa Cancelar.)"
            )
        return

    # b) Está respondiendo a "¿qué cambio?" de una oportunidad YA publicada (edición).
    if isinstance(awaiting, dict) and awaiting.get("edit"):
        identifier = awaiting["edit"]
        ctx.user_data.pop("awaiting", None)
        result = await pipeline.edit_published(identifier, raw, user.id)
        if result["status"] == "edited":
            await update.message.reply_text(
                "✅ <b>Actualizada.</b> El mapa y la lista ya reflejan el cambio (el mensaje que ya "
                "salió en el canal se queda como estaba).\n\nAsí queda ahora:\n\n"
                + pub.format_opportunity(result["opp"]),
                parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            )
        elif result["status"] in ("not_found", "forbidden"):
            await update.message.reply_text("🚫 No puedo editar esa oportunidad (o no es tuya).")
        else:
            await update.message.reply_text(f"⚠️ {result.get('error') or 'No pude aplicar el cambio.'}")
        return

    # c) Envío nuevo → preview con confirmación.
    log.info("Procesando mensaje de %s (@%s)", user.id, user.username)
    result = await pipeline.preview(raw, user.id)
    status = result["status"]

    if status == "ready":
        ctx.user_data["pending"] = {"raw_text": raw, "corrections": []}
        await _show_preview(update.message, ctx, result)
    elif status == "error":
        await alerts.alert(
            "Error procesando una oportunidad",
            f"Usuario {user.id} (@{user.username}): {result.get('error')}",
            key="pipeline_error",
        )
        await update.message.reply_text(f"⚠️ {result.get('error') or 'Error procesando el mensaje.'}")
    else:
        await update.message.reply_text(_reject_text(result) or "No he podido procesar el mensaje.")


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Botones de la vista previa (Enviar/Modificar/Cancelar) y de edición/eliminación
    (/editarmisproyectos)."""
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""
    await query.answer()

    if data == "cancel":
        ctx.user_data.pop("pending", None)
        ctx.user_data.pop("awaiting", None)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("❌ Cancelada. No se ha publicado nada.")
        return

    if data == "modify":
        if not ctx.user_data.get("pending"):
            await query.message.reply_text("No hay ninguna ficha pendiente. Mándame la oportunidad otra vez.")
            return
        ctx.user_data["awaiting"] = "modify"
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✏️ Dime qué cambio en un mensaje. Por ejemplo:\n"
            "• «la fecha de fin es el 20 de septiembre»\n"
            "• «el país es Italia, no España»\n"
            "• «añade el enlace https://…»"
        )
        return

    if data == "send":
        pend = ctx.user_data.get("pending")
        if not pend or not pend.get("fields"):
            await query.message.reply_text("Esa ficha ya no está disponible. Mándame la oportunidad otra vez.")
            return
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.chat.send_action("typing")
        result = await pipeline.commit(
            pend["fields"], source="gestor",
            submitted_by=f"{user.full_name} (@{user.username})", submitted_by_id=user.id,
        )
        ctx.user_data.pop("pending", None)
        ctx.user_data.pop("awaiting", None)
        if result["status"] == "created" and result.get("published"):
            await query.message.reply_text("✅ ¡Publicada en el canal! Gracias por contribuir. 🙌")
        elif result["status"] == "created":
            await query.message.reply_text("💾 Guardada (aún no hay canal configurado para publicar).")
        elif result["status"] == "created_no_publish":
            await query.message.reply_text(
                f"⚠️ No se pudo publicar ({result.get('error')}). Ya he avisado a {_CONTACT} para "
                "arreglarlo. Puedes volver a mandarme el mismo texto cuando quieras — no se ha "
                "quedado a medias bloqueando el reenvío."
            )
            await alerts.alert("Falló publicar tras confirmar", str(result.get("error")), key="commit_publish")
        else:
            await query.message.reply_text(f"⚠️ {result.get('error') or 'No pude publicarla.'}")
        return

    if data.startswith("edit:"):
        identifier = data.split(":", 1)[1]
        opp = await repo.get_by_identifier(identifier)
        if not opp or (opp.get("submitted_by_id") != user.id and not await repo.is_admin(user.id)):
            await query.message.reply_text("🚫 No puedo editar esa oportunidad (o no es tuya).")
            return
        ctx.user_data["awaiting"] = {"edit": identifier}
        await query.message.reply_text(
            f"✏️ Editando «{opp['title']}». Dime qué cambio en un mensaje "
            "(p.ej. «cambia la fecha de fin al 20 de septiembre» o «corrige el país a Italia»).\n\n"
            "Solo cambiará en el mapa y la lista; el mensaje que ya salió en el canal se queda igual."
        )
        return

    # Eliminar: paso 1, pide confirmación (acción difícil de deshacer para el coordinador
    # — no hay otro botón para volver a abrirla, solo un admin podría reabrirla a mano).
    if data.startswith("del:"):
        identifier = data.split(":", 1)[1]
        opp = await repo.get_by_identifier(identifier)
        if not opp or (opp.get("submitted_by_id") != user.id and not await repo.is_admin(user.id)):
            await query.message.reply_text("🚫 No puedo eliminar esa oportunidad (o no es tuya).")
            return
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑️ Sí, eliminar", callback_data=f"delyes:{identifier}"),
            InlineKeyboardButton("↩️ No", callback_data=f"delno:{identifier}"),
        ]]))
        await query.message.reply_text(
            f"⚠️ ¿Seguro que quieres eliminar «{opp['title']}»? Desaparecerá del mapa y la lista. "
            "El mensaje que ya salió en el canal de Telegram no se puede retirar y se queda como estaba."
        )
        return

    if data.startswith("delyes:"):
        identifier = data.split(":", 1)[1]
        result = await pipeline.delete_published(identifier, user.id)
        if result["status"] == "deleted":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"🗑️ Eliminada «{result['opp']['title']}».")
        elif result["status"] == "already_closed":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Esa oportunidad ya no estaba abierta (puede que ya se hubiera eliminado o expirado).")
        elif result["status"] in ("not_found", "forbidden"):
            await query.message.reply_text("🚫 No he podido eliminarla (o no es tuya).")
        else:
            await query.message.reply_text(f"⚠️ {result.get('error') or 'No pude eliminarla.'}")
        return

    if data.startswith("delno:"):
        identifier = data.split(":", 1)[1]
        opp = await repo.get_by_identifier(identifier)
        if opp:
            await query.edit_message_reply_markup(reply_markup=_project_keyboard(identifier))
        await query.message.reply_text("Vale, no se elimina.")
        return


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Red de seguridad: cualquier excepción no capturada en un handler llega aquí.
    Sin esto, un fallo dejaba al usuario sin respuesta y al admin sin enterarse."""
    log.exception("Excepción no capturada en un handler", exc_info=ctx.error)
    await alerts.alert(
        "Error no controlado en el bot",
        f"{type(ctx.error).__name__}: {ctx.error}",
        key="bot_unhandled",
    )
    msg = getattr(update, "message", None)
    if msg:
        try:
            await msg.reply_text(
                f"⚠️ Se me ha ido algo. Ya he avisado a {_CONTACT}; inténtalo de nuevo en un rato."
            )
        except Exception:  # noqa: BLE001
            pass


async def _post_init(app: Application) -> None:
    await open_pool()
    log.info("Pool de Postgres abierto.")
    await app.bot.set_my_commands([
        ("start", "Info y cómo funciona el bot"),
        ("ayuda", "Ver todos los comandos disponibles"),
        ("editarmisproyectos", "Editar o eliminar tus oportunidades abiertas"),
        ("historicomisproyectos", "Histórico de todo lo que has publicado"),
    ])


async def _post_shutdown(_app: Application) -> None:
    await close_pool()


def build_application() -> Application:
    app = (
        Application.builder()
        .token(cfg.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("editarmisproyectos", cmd_editarmisproyectos))
    app.add_handler(CommandHandler("historicomisproyectos", cmd_historicomisproyectos))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_submission))
    app.add_error_handler(on_error)
    return app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not cfg.telegram_bot_token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el entorno (.env).")
    # callback_query hace falta para los botones Enviar/Modificar/Cancelar y Editar.
    build_application().run_polling(allowed_updates=["message", "callback_query"])
