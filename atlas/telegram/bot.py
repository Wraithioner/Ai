"""Telegram bot interface — connects Brain + Arena to Telegram users."""

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
from atlas.arena.client import ArenaClient

logger = logging.getLogger(__name__)


class TelegramBot:
    """Handles Telegram messages and routes them to the Brain.

    Features:
    - Per-user conversation memory (managed by Brain)
    - Owner/admin commands for Arena operations
    - Rate limiting per user
    - Typing indicator while generating
    """

    def __init__(self, brain: Brain, config: dict, arena: ArenaClient | None = None):
        self.brain = brain
        self.config = config
        self.arena = arena

        tg_cfg = config.get("telegram", {})
        self.bot_token = tg_cfg.get("bot_token", "")
        self.owner_id = tg_cfg.get("owner_id", 0)

        safety_cfg = config.get("safety", {})
        self.rate_limit = safety_cfg.get("max_messages_per_minute", 15)
        self._user_timestamps: dict[int, list[float]] = defaultdict(list)

    def _is_owner(self, user_id: int) -> bool:
        return self.owner_id and user_id == self.owner_id

    def _check_rate_limit(self, user_id: int) -> bool:
        if self._is_owner(user_id):
            return True

        now = time.time()
        timestamps = self._user_timestamps[user_id]
        self._user_timestamps[user_id] = [t for t in timestamps if now - t < 60]

        if len(self._user_timestamps[user_id]) >= self.rate_limit:
            return False

        self._user_timestamps[user_id].append(now)
        return True

    # ---- Public commands ----

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Hello! Send me a message and I'll respond.\n\n"
            "Commands:\n"
            "/reset - Clear conversation memory\n"
            "/help - Show this message"
        )

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.brain.reset_conversation(user_id)
        await update.message.reply_text("Memory cleared.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "Send me any message and I'll respond.\n\n"
            "Commands:\n"
            "/reset - Clear conversation memory\n"
            "/help - Show this message"
        )
        if self._is_owner(update.effective_user.id):
            text += (
                "\n\nOwner commands:\n"
                "/status - Bot & Arena stats\n"
                "/arena_post <text> - Post to Arena\n"
                "/arena_reply <thread_id> <text> - Reply to a thread\n"
                "/arena_feed - View your Arena feed\n"
                "/arena_stats - Share/earnings stats\n"
                "/arena_me - Your Arena profile"
            )
        await update.message.reply_text(text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i + 4096])
        else:
            await update.message.reply_text(response)

    # ---- Owner commands ----

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot + Arena stats (owner only)."""
        if not self._is_owner(update.effective_user.id):
            return

        lines = [
            f"Active users: {self.brain.active_users()}/{self.brain.max_users}",
            f"Model: {self.brain.model_name}",
            f"Device: {self.brain.device}",
        ]

        if self.arena and self.arena.configured:
            lines.append(f"Arena handle: {self.arena.handle}")
            stats = self.arena.get_share_stats()
            if stats:
                lines.append(f"Arena shares: {stats}")
        else:
            lines.append("Arena: not configured")

        await update.message.reply_text("\n".join(lines))

    async def cmd_arena_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post to Arena (owner only). Usage: /arena_post <content>"""
        if not self._is_owner(update.effective_user.id):
            return
        if not self.arena or not self.arena.configured:
            await update.message.reply_text("Arena not configured.")
            return

        text = update.message.text.replace("/arena_post", "", 1).strip()
        if not text:
            await update.message.reply_text("Usage: /arena_post <content>")
            return

        result = self.arena.create_thread(f"<p>{text}</p>")
        if result:
            await update.message.reply_text(f"Posted to Arena.")
        else:
            await update.message.reply_text("Failed to post.")

    async def cmd_arena_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reply to Arena thread (owner only). Usage: /arena_reply <thread_id> <content>"""
        if not self._is_owner(update.effective_user.id):
            return
        if not self.arena or not self.arena.configured:
            await update.message.reply_text("Arena not configured.")
            return

        parts = update.message.text.replace("/arena_reply", "", 1).strip().split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("Usage: /arena_reply <thread_id> <content>")
            return

        thread_id, content = parts
        result = self.arena.reply_to_thread(thread_id, f"<p>{content}</p>")
        if result:
            await update.message.reply_text("Reply posted.")
        else:
            await update.message.reply_text("Failed to reply.")

    async def cmd_arena_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View Arena feed (owner only)."""
        if not self._is_owner(update.effective_user.id):
            return
        if not self.arena or not self.arena.configured:
            await update.message.reply_text("Arena not configured.")
            return

        feed = self.arena.get_my_feed()
        if not feed:
            await update.message.reply_text("Could not load feed.")
            return

        # Format feed items
        if isinstance(feed, list):
            lines = []
            for item in feed[:10]:
                text = item.get("content", "")[:100] if isinstance(item, dict) else str(item)[:100]
                lines.append(f"- {text}")
            await update.message.reply_text("\n".join(lines) or "Feed is empty.")
        else:
            await update.message.reply_text(str(feed)[:4096])

    async def cmd_arena_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Arena share/earnings stats (owner only)."""
        if not self._is_owner(update.effective_user.id):
            return
        if not self.arena or not self.arena.configured:
            await update.message.reply_text("Arena not configured.")
            return

        stats = self.arena.get_share_stats()
        holdings = self.arena.get_holdings()
        earnings = self.arena.get_earnings()

        lines = ["Arena Stats:"]
        if stats:
            lines.append(f"Shares: {stats}")
        if holdings:
            lines.append(f"Holdings: {holdings}")
        if earnings:
            lines.append(f"Earnings: {earnings}")

        await update.message.reply_text("\n".join(lines)[:4096])

    async def cmd_arena_me(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View Arena agent profile (owner only)."""
        if not self._is_owner(update.effective_user.id):
            return
        if not self.arena or not self.arena.configured:
            await update.message.reply_text("Arena not configured.")
            return

        profile = self.arena.get_me()
        if profile:
            await update.message.reply_text(str(profile)[:4096])
        else:
            await update.message.reply_text("Could not load profile.")

    # ---- App setup ----

    def build_app(self) -> Application:
        if not self.bot_token:
            raise ValueError("No bot token. Set TELEGRAM_BOT_TOKEN env var on Railway.")

        app = Application.builder().token(self.bot_token).build()

        # Public commands
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("reset", self.cmd_reset))
        app.add_handler(CommandHandler("help", self.cmd_help))

        # Owner commands
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("arena_post", self.cmd_arena_post))
        app.add_handler(CommandHandler("arena_reply", self.cmd_arena_reply))
        app.add_handler(CommandHandler("arena_feed", self.cmd_arena_feed))
        app.add_handler(CommandHandler("arena_stats", self.cmd_arena_stats))
        app.add_handler(CommandHandler("arena_me", self.cmd_arena_me))

        # Message handler (last — catches everything else)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        return app

    def run(self):
        app = self.build_app()
        logger.info("Telegram bot starting (polling mode)...")
        app.run_polling(drop_pending_updates=True)
