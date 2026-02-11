"""Telegram bot interface — connects the agent engine to Telegram."""

import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from agent.engine import handle_message, HELP_TEXT
from agent.modules import scheduler
from agent.utils.config import TELEGRAM_BOT_TOKEN, OWNER_ID

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
_app = None


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized. If OWNER_ID is 0, allow everyone."""
    return OWNER_ID == 0 or user_id == OWNER_ID


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    if not is_authorized(user.id):
        await update.message.reply_text(
            f"Unauthorized. Your ID: `{user.id}`\n"
            "Set OWNER_ID in Railway to this value to authorize.",
            parse_mode="Markdown",
        )
        return
    welcome = f"Hey **{user.first_name}**! I'm your personal agent.\n\n{HELP_TEXT}"
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def on_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /id command — show user's Telegram ID."""
    user = update.effective_user
    await update.message.reply_text(
        f"Your Telegram ID: `{user.id}`\n"
        f"Name: {user.first_name} {user.last_name or ''}\n"
        f"Username: @{user.username or 'none'}",
        parse_mode="Markdown",
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not is_authorized(user.id):
        await update.message.reply_text(f"Unauthorized. Your ID: `{user.id}`", parse_mode="Markdown")
        return

    user_text = update.message.text
    logger.info(f"[{user.id} @{user.username}] {user_text}")

    # Show "typing" while processing
    await update.message.chat.send_action("typing")

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

    chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)


async def _send_reminder(message: str):
    """Send a reminder message to the owner via Telegram."""
    if not _app or OWNER_ID == 0:
        logger.warning("Cannot send reminder: no app or OWNER_ID not set")
        return
    try:
        text = f"**Reminder**\n\n{message}"
        await _app.bot.send_message(chat_id=OWNER_ID, text=text, parse_mode="Markdown")
        logger.info(f"Reminder sent: {message}")
    except Exception as e:
        logger.error(f"Failed to send reminder: {e}")


async def _post_init(application: Application):
    """Run after the bot starts — set up commands and scheduler."""
    global _app
    _app = application

    # Set bot commands menu
    commands = [
        BotCommand("help", "Show all commands"),
        BotCommand("run", "Execute a shell command"),
        BotCommand("sysinfo", "System information"),
        BotCommand("ls", "List directory"),
        BotCommand("read", "Read a file"),
        BotCommand("fetch", "Fetch a webpage"),
        BotCommand("note", "Save a note"),
        BotCommand("notes", "List notes"),
        BotCommand("remind", "Set a reminder"),
        BotCommand("ping", "Check if alive"),
        BotCommand("id", "Show your Telegram ID"),
        BotCommand("uptime", "Bot uptime"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu set")

    # Start reminder scheduler
    scheduler.register_callback(_send_reminder)
    asyncio.create_task(scheduler.start_scheduler())
    logger.info("Scheduler started")


def run_bot():
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set. Add it in Railway environment variables.")

    logger.info("Starting bot...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    # Register handlers
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_start))
    app.add_handler(CommandHandler("id", on_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.COMMAND, on_message))

    logger.info("Bot is running. Polling for messages...")
    app.run_polling(drop_pending_updates=True)
