"""Telegram bot interface — connects the agent engine to Telegram."""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from agent.engine import handle_message, HELP_TEXT
from agent.utils.config import TELEGRAM_BOT_TOKEN, OWNER_ID

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized. If OWNER_ID is 0, allow everyone."""
    return OWNER_ID == 0 or user_id == OWNER_ID


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized. Set OWNER_ID in Railway to your Telegram user ID.")
        return
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages."""
    if not update.message or not update.message.text:
        return

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_text = update.message.text
    logger.info(f"[{update.effective_user.id}] {user_text}")

    response = await handle_message(user_text)
    await _send_response(update, response)


async def _send_response(update: Update, text: str):
    """Send response, splitting if too long for Telegram."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        try:
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(text)
        return

    # Split long messages
    chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)


def run_bot():
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set. Add it in Railway environment variables.")

    logger.info("Starting bot...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.COMMAND, on_message))

    logger.info("Bot is running. Polling for messages...")
    app.run_polling(drop_pending_updates=True)
