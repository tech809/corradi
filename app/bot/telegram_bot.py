"""Bot de captura de oportunidades en Telegram (acceso abierto + LLM + dedup + publicación)."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

from app import pipeline
from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, open_pool
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.bot")

_CONTACT = "@pachums97"


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola 👋 Soy el bot de CORRADI-BOT: alimento el canal de difusión de Corradi Erasmus+.\n\n"
        "¿Cómo funciona? Pégame el mensaje de una oportunidad tal cual lo tengas y se publica "
        "en el canal.\n\n"
        f"⚠️ Manda solo oportunidades reales, una por mensaje (máximo "
        f"{cfg.max_daily_opportunities} al día). Si mandas algo que no es una oportunidad te "
        "aviso; si se repite, se bloquea el acceso automáticamente.\n\n"
        "Usa /ayuda para ver el resto de comandos.",
    )


async def cmd_ayuda(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 <b>Comandos de CORRADI-BOT</b>\n\n"
        "<b>Para publicar una oportunidad:</b> pégame el texto tal cual (con emojis, sin "
        "limpiar nada), no hace falta ningún comando. Compruebo que es una oportunidad real, "
        "extraigo título/fechas/país/deadline/formulario, reviso que no esté repetida y la "
        "publico sola en el canal.\n\n"
        "📋 <b>Reglas:</b>\n"
        "• Una oportunidad por mensaje (si tienes varias, mándalas por separado)\n"
        f"• Máximo {cfg.max_daily_opportunities} al día\n"
        "• Solo oportunidades reales — si mandas algo que no lo es, te aviso; si se repite, "
        "se bloquea el acceso automáticamente\n\n"
        "🔎 <b>/buscar &lt;palabra&gt;</b> — busca entre las oportunidades abiertas (país, tema, título...)\n"
        "📊 <b>/misenvios</b> — cuántas has mandado hoy y tu historial reciente\n\n"
        '🌍 Canal de difusión: <a href="https://t.me/erasmuscorradi">t.me/erasmuscorradi</a>\n\n'
        f"¿Dudas o algún error (p.ej. bloqueo injusto)? Contacta con {_CONTACT}.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_buscar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Uso: /buscar <palabra> (país, tema, título...)")
        return
    q = " ".join(ctx.args)
    results = await repo.search(q=q, limit=8)
    if not results:
        await update.message.reply_text(f"🔎 No he encontrado nada abierto para «{q}».")
        return
    parts = [f"🔎 <b>Resultados para «{q}»</b> ({len(results)})"]
    parts += [pub.format_summary_item(o) for o in results]
    await update.message.reply_text(
        "\n\n".join(parts), parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


async def cmd_misenvios(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    is_admin = await repo.is_admin(user.id)
    if is_admin:
        limit_text = "sin límite (admin)"
    else:
        today_count = await repo.count_created_since(user.id, pipeline.today_start())
        limit_text = f"{today_count}/{cfg.max_daily_opportunities} hoy"

    rows = await repo.list_recent_submissions(user.id, limit=5)
    icons = {
        "created": "✅", "duplicate": "♻️", "duplicate_similar": "♻️",
        "not_opportunity": "🤔", "rate_limited": "⏳", "error": "⚠️",
    }
    lines = [f"📊 <b>Tus envíos:</b> {limit_text}\n"]
    if not rows:
        lines.append("Todavía no has mandado nada.")
    else:
        lines.append("<b>Últimos envíos:</b>")
        for r in rows:
            when = r["created"].astimezone(ZoneInfo(cfg.timezone)).strftime("%d/%m %H:%M")
            icon = icons.get(r["status"], "•")
            title = f" — {r['title']}" if r.get("title") else ""
            lines.append(f"{icon} {when}{title}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_id(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Devuelve el ID numérico de Telegram (para ponerlo en ADMIN_TELEGRAM_IDS)."""
    u = update.effective_user
    await update.message.reply_text(
        f"Tu ID de Telegram es <code>{u.id}</code>\n"
        f"(usuario: @{u.username} · {u.full_name})",
        parse_mode=ParseMode.HTML,
    )


async def cmd_privacidad(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🔒 <b>Privacidad de CORRADI-BOT</b>\n\n"
        "Difundimos oportunidades Erasmus+ para jóvenes. Tratamos el texto público de las "
        "convocatorias y, de quien las envía, su usuario de Telegram para poder atender "
        "incidencias. No vendemos datos. El texto se procesa con un LLM solo para "
        "estructurarlo. Puedes ejercer tus derechos en privacidad@proactivefuture.org.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def on_submission(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await repo.is_blocked(user.id):
        log.info("Mensaje rechazado: %s (@%s) está bloqueado", user.id, user.username)
        await update.message.reply_text(
            f"🚫 Tu acceso está bloqueado. Si crees que es un error, contacta con {_CONTACT}."
        )
        return

    raw = update.message.text
    await update.message.chat.send_action("typing")
    log.info("Procesando mensaje de %s (@%s)", user.id, user.username)

    result = await pipeline.ingest(
        raw, source="gestor", submitted_by=f"{user.full_name} (@{user.username})",
        submitted_by_id=user.id,
    )
    status = result["status"]

    if status == "rate_limited":
        await update.message.reply_text(
            f"⏳ Ya has mandado {result['limit']} oportunidades hoy, el máximo diario. "
            "Vuelve a intentarlo mañana."
        )
    elif status == "not_opportunity":
        if result.get("blocked"):
            await update.message.reply_text(
                "🚫 Se ha bloqueado tu acceso automáticamente por mandar dos mensajes seguidos "
                f"que no son oportunidades. Si crees que es un error, contacta con {_CONTACT}."
            )
        else:
            text = f"🤔 No parece una oportunidad. Motivo: {result.get('reason') or '—'}"
            if result.get("warn"):
                text += "\n\n⚠️ Aviso: si vuelve a pasar, se bloqueará tu acceso automáticamente."
            await update.message.reply_text(text)
    elif status == "duplicate":
        ex = result["existing"]
        await update.message.reply_text(f"♻️ Ya existe: «{ex['title']}». No la republico.")
    elif status == "duplicate_similar":
        dup = result["dup"]
        await update.message.reply_text(
            f"♻️ Muy parecida ({dup['similarity']:.0%}) a «{dup['title']}». No la republico."
        )
    elif status in ("created", "created_no_publish"):
        opp = result["opp"]
        if status == "created" and result.get("published"):
            estado = "✅ Publicada en el canal de Telegram."
        elif status == "created":
            estado = "💾 Guardada (aún no hay canal configurado: define TELEGRAM_CHANNEL_ID para publicar)."
        else:
            estado = f"💾 Guardada, pero falló la publicación/handoff: {result.get('error')}"
        await update.message.reply_text(
            f"{estado}\n\nAsí queda:\n\n{pub.format_opportunity(opp)}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    else:  # error
        await update.message.reply_text(f"⚠️ {result.get('error') or 'Error procesando el mensaje.'}")


async def _post_init(app: Application) -> None:
    await open_pool()
    log.info("Pool de Postgres abierto.")
    await app.bot.set_my_commands([
        ("start", "Info y cómo funciona el bot"),
        ("ayuda", "Ver todos los comandos disponibles"),
        ("buscar", "Buscar entre las oportunidades abiertas"),
        ("misenvios", "Ver cuántas has mandado hoy y tu historial"),
        ("id", "Ver tu ID numérico de Telegram"),
        ("privacidad", "Política de privacidad"),
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
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CommandHandler("misenvios", cmd_misenvios))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("privacidad", cmd_privacidad))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_submission))
    return app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not cfg.telegram_bot_token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el entorno (.env).")
    build_application().run_polling(allowed_updates=["message"])
