"""Telegram bot interface — connects the Brain to Telegram users."""

import logging
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from atlas.core.brain import Brain

logger = logging.getLogger(__name__)


class TelegramBot:
    """Handles Telegram messages and routes them to the Brain.

    Features:
    - Per-user conversation memory (managed by Brain)
    - Owner/admin commands (/status)
    - Rate limiting per user
    - Typing indicator while generating
    """

    def __init__(self, brain: Brain, config: dict):
        self.brain = brain
        self.config = config

        tg_cfg = config.get("telegram", {})
        self.bot_token = tg_cfg.get("bot_token", "")
        self.owner_id = tg_cfg.get("owner_id", 0)

        safety_cfg = config.get("safety", {})
        self.rate_limit = safety_cfg.get("max_messages_per_minute", 15)
        self._user_timestamps: dict[int, list[float]] = defaultdict(list)

    def _is_owner(self, user_id: int) -> bool:
        """Check if a user is the bot owner."""
        return self.owner_id and user_id == self.owner_id

    def _check_rate_limit(self, user_id: int) -> bool:
        """Return True if the user is within rate limits. Owner bypasses."""
        if self._is_owner(user_id):
            return True

        now = time.time()
        timestamps = self._user_timestamps[user_id]
        self._user_timestamps[user_id] = [t for t in timestamps if now - t < 60]

        if len(self._user_timestamps[user_id]) >= self.rate_limit:
            return False

        self._user_timestamps[user_id].append(now)
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "Hello! Send me a message and I'll respond.\n\n"
            "Commands:\n"
            "/reset - Clear conversation memory\n"
            "/help - Show this message"
        )

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command."""
        user_id = update.effective_user.id
        self.brain.reset_conversation(user_id)
        await update.message.reply_text("Memory cleared.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        text = (
            "Send me any message and I'll respond.\n\n"
            "Commands:\n"
            "/reset - Clear conversation memory\n"
            "/help - Show this message"
        )
        if self._is_owner(update.effective_user.id):
            text += "\n\nOwner commands:\n/status - Bot stats"

        await update.message.reply_text(text)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command (owner only)."""
        user_id = update.effective_user.id
        if not self._is_owner(user_id):
            return

        active = self.brain.active_users()
        max_u = self.brain.max_users
        model = self.brain.model_name
        device = self.brain.device

        arena_cfg = self.config.get("arena", {})
        arena_handle = arena_cfg.get("handle", "not set")

        await update.message.reply_text(
            f"Active users: {active}/{max_u}\n"
            f"Model: {model}\n"
            f"Device: {device}\n"
            f"Arena: {arena_handle}"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        text = update.message.text.strip()

        if not text:
            return

        if not self._check_rate_limit(user_id):
            await update.message.reply_text("Slow down — too many messages. Wait a moment.")
            return

        await update.message.chat.send_action("typing")

        try:
            response = self.brain.think(text, user_id=user_id)
        except Exception as e:
            logger.error("Error for user %d: %s", user_id, e)
            response = "Something went wrong. Try again."

        # Telegram 4096 char limit
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i + 4096])
        else:
            await update.message.reply_text(response)

    def build_app(self) -> Application:
        """Build and return the Telegram Application."""
        if not self.bot_token:
            raise ValueError(
                "No bot token. Set TELEGRAM_BOT_TOKEN env var on Railway."
            )

        app = Application.builder().token(self.bot_token).build()

        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("reset", self.cmd_reset))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        return app

    def run(self):
        """Start the bot with polling (suitable for Railway)."""
        app = self.build_app()
        logger.info("Telegram bot starting (polling mode)...")
        app.run_polling(drop_pending_updates=True)
