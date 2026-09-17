"""Public read-only bot for browsing the isolated Corradi World catalogue."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import cfg
from app.db import world_repository as world_repo
from app.db.pool import close_pool, open_pool
from app.publisher.world_telegram import format_opportunity
from app.sources.salto_world import PROGRAMME_COUNTRY_CODES, NEIGHBOURING_COUNTRY_CODES

log = logging.getLogger("corradi.world_discovery_bot")
_KNOWN_CODES = PROGRAMME_COUNTRY_CODES | NEIGHBOURING_COUNTRY_CODES


async def start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌍 <b>Welcome to Corradi World</b>\n\n"
        "I help you discover open European training opportunities.\n\n"
        "Use /latest for the newest calls or /country ES (replace ES with your country "
        "code) to see opportunities matching your residence.\n\n"
        "Web catalogue: https://mapa.proactivefuture.eu/world",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def latest(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    rows = (await world_repo.list_open())[:5]
    if not rows:
        await update.message.reply_text("There are no open opportunities in the catalogue yet.")
        return
    for row in rows:
        await update.message.reply_text(
            format_opportunity(row), parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )


async def country(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    code = (ctx.args[0] if ctx.args else "").strip().upper()
    if code not in _KNOWN_CODES:
        await update.message.reply_text("Use a two-letter country code, for example /country RO.")
        return
    rows = (await world_repo.list_open(residence=code))[:10]
    if not rows:
        await update.message.reply_text(
            f"No open calls match {code} right now. Check again soon: the catalogue updates daily."
        )
        return
    await update.message.reply_text(f"<b>{len(rows)} current matches for {code}</b>", parse_mode=ParseMode.HTML)
    for row in rows:
        await update.message.reply_text(
            format_opportunity(row), parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )


async def _startup(_application: Application) -> None:
    await open_pool()


async def _shutdown(_application: Application) -> None:
    await close_pool()


def run() -> None:
    if not cfg.world_telegram_bot_token:
        raise RuntimeError("WORLD_TELEGRAM_BOT_TOKEN is not configured")
    app = (
        Application.builder().token(cfg.world_telegram_bot_token)
        .post_init(_startup).post_shutdown(_shutdown).build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CommandHandler("country", country))
    log.info("Corradi World discovery bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    run()
