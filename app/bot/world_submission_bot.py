"""Private English ingestion bot for manually adding Corradi World opportunities."""
from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import cfg
from app.db import world_repository as world_repo
from app.db.pool import close_pool, open_pool
from app.llm import extractor
from app.publisher.world_telegram import format_opportunity
from app.sources.salto_world import parse_eligibility_label

log = logging.getLogger("corradi.world_submission_bot")
_ACTIONS = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Save", callback_data="world:save"),
    InlineKeyboardButton("❌ Cancel", callback_data="world:cancel"),
]])


async def _flush_usage_safely() -> None:
    """Do not lose a valid submission because optional cost accounting is unavailable."""
    try:
        await extractor.flush_usage()
    except Exception:  # noqa: BLE001
        log.warning("Could not persist World extraction usage", exc_info=True)


def _allowed(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in cfg.admin_telegram_ids)


async def start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        await update.message.reply_text("This contribution bot is currently in private testing.")
        return
    await update.message.reply_text(
        "Send one English Training Course announcement per message. I will extract an "
        "English preview and save it only to Corradi World after your confirmation."
    )


async def submission(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        await update.message.reply_text("This contribution bot is currently in private testing.")
        return
    await update.message.chat.send_action("typing")
    raw = update.message.text
    try:
        fields = await asyncio.to_thread(extractor.extract_world, raw)
    finally:
        await _flush_usage_safely()
    if not fields.get("is_opportunity") or fields.get("type") != "TRAINING_COURSE":
        await update.message.reply_text(
            "I could not validate this as an open Training Course. "
            + str(fields.get("reason") or "Please check the source and send one call at a time.")
        )
        return
    if fields.get("deadline_in_past") or fields.get("is_online"):
        await update.message.reply_text("This call is expired or online-only, so it was not saved.")
        return
    ctx.user_data["world_pending"] = fields
    await update.message.reply_text(
        "<b>Review before saving to /world</b>\n\n" + format_opportunity(fields, include_source=False),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=_ACTIONS,
    )


async def action(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _allowed(update):
        return
    if query.data == "world:cancel":
        ctx.user_data.pop("world_pending", None)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Cancelled. Nothing was saved.")
        return
    fields = ctx.user_data.pop("world_pending", None)
    if not fields:
        await query.message.reply_text("The preview expired. Send the announcement again.")
        return
    codes, scope = parse_eligibility_label(fields.get("eligibility_countries"))
    project = await world_repo.insert_manual_project(fields, update.effective_user.id, codes, scope)
    await query.edit_message_reply_markup(reply_markup=None)
    if cfg.world_telegram_channel_id:
        sent = await ctx.bot.send_message(
            chat_id=cfg.world_telegram_channel_id,
            text=format_opportunity(project, include_source=False),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        await world_repo.set_telegram_message(project["identifier"], sent.message_id)
    await query.message.reply_text(
        f"✅ Saved as {project['identifier']} in https://mapa.proactivefuture.eu/world"
    )


async def _startup(_application: Application) -> None:
    await open_pool()


async def _shutdown(_application: Application) -> None:
    await close_pool()


def run() -> None:
    if not cfg.world_submission_bot_token:
        raise RuntimeError("WORLD_SUBMISSION_BOT_TOKEN is not configured")
    app = (
        Application.builder().token(cfg.world_submission_bot_token)
        .post_init(_startup).post_shutdown(_shutdown).build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(action, pattern=r"^world:(save|cancel)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, submission))
    log.info("Corradi World submission bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    run()
