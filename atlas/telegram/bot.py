"""Telegram bot interface — connects Brain + Arena to the bot owner via Telegram.

OWNER-ONLY: Only the configured OWNER_ID can interact with this bot.
All other users are silently ignored.
"""

import asyncio
import html
import logging
import re
import time
import traceback
from collections import defaultdict

from telegram import BotCommand, Update
from telegram.constants import ParseMode
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

# Telegram message limit
TG_MSG_LIMIT = 4096
# Max input message length to prevent OOM during tokenization
MAX_INPUT_LENGTH = 4000


def escape(text: str) -> str:
    """Escape text for HTML parse mode."""
    return html.escape(text)


async def send_long(update: Update, text: str, parse_mode: str | None = None):
    """Send a message, splitting into chunks if over 4096 chars."""
    if len(text) <= TG_MSG_LIMIT:
        await update.message.reply_text(text, parse_mode=parse_mode)
        return
    # Split on newlines to avoid breaking mid-tag
    chunks = []
    current = ""
    for line in text.split("\n"):
        # If a single line exceeds the limit, hard-split it
        while len(line) > TG_MSG_LIMIT:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:TG_MSG_LIMIT])
            line = line[TG_MSG_LIMIT:]
        if len(current) + len(line) + 1 > TG_MSG_LIMIT:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode=parse_mode)


class TelegramBot:
    """Owner-only Telegram bot with LLM brain and Arena integration.

    Security: Every handler checks OWNER_ID first. Non-owners are silently ignored.
    Async safety: brain.think() runs via asyncio.to_thread() to avoid blocking the event loop.
    """

    def __init__(self, brain: Brain, config: dict, arena: ArenaClient | None = None):
        self.brain = brain
        self.config = config
        self.arena = arena

        tg_cfg = config.get("telegram", {})
        self.bot_token = tg_cfg.get("bot_token", "")
        self.owner_id = tg_cfg.get("owner_id", 0)

        safety_cfg = config.get("safety", {})
        self._rate_limit = safety_cfg.get("max_messages_per_minute", 15) if safety_cfg.get("enabled", True) else 0
        self._msg_timestamps: defaultdict[int, list[float]] = defaultdict(list)

    def _is_owner(self, update: Update) -> bool:
        """Check if the message is from the owner. Silently reject everyone else."""
        if not update.effective_user:
            return False
        return bool(self.owner_id and update.effective_user.id == self.owner_id)

    def _is_rate_limited(self, user_id: int) -> bool:
        """Check if a user has exceeded the per-minute message rate limit."""
        if not self._rate_limit:
            return False
        now = time.monotonic()
        timestamps = self._msg_timestamps[user_id]
        # Prune timestamps older than 60 seconds
        cutoff = now - 60
        self._msg_timestamps[user_id] = [t for t in timestamps if t > cutoff]
        if len(self._msg_timestamps[user_id]) >= self._rate_limit:
            return True
        self._msg_timestamps[user_id].append(now)
        return False

    # ================================================================
    # PUBLIC COMMANDS (owner-gated)
    # ================================================================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        text = (
            "<b>Agent Bot Online</b>\n\n"
            "Send any message and I'll respond with AI.\n\n"
            "<b>Commands:</b>\n"
            "/reset - Clear conversation memory\n"
            "/status - Bot & Arena stats\n"
            "/help - Full command list"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        text = (
            "<b>Commands</b>\n\n"
            "<b>General:</b>\n"
            "/start - Welcome message\n"
            "/reset - Clear conversation memory\n"
            "/status - Bot & model stats\n"
            "/help - This message\n\n"
            "<b>Arena — Posts:</b>\n"
            "/post &lt;text&gt; - Create a post\n"
            "/reply &lt;thread_id&gt; &lt;text&gt; - Reply to a thread\n"
            "/delete_post &lt;thread_id&gt; - Delete a post\n"
            "/like &lt;thread_id&gt; - Like a thread\n"
            "/repost &lt;thread_id&gt; - Repost a thread\n"
            "/quote &lt;thread_id&gt; &lt;text&gt; - Quote-repost\n\n"
            "<b>Arena — Feeds:</b>\n"
            "/feed - Your feed\n"
            "/trending - Trending feed\n"
            "/userfeed &lt;handle&gt; - User's posts\n\n"
            "<b>Arena — Social:</b>\n"
            "/follow &lt;user_id&gt; - Follow a user\n"
            "/unfollow &lt;user_id&gt; - Unfollow a user\n"
            "/followers - Your followers\n"
            "/following - Who you follow\n"
            "/search &lt;query&gt; - Search users\n\n"
            "<b>Arena — Profile:</b>\n"
            "/me - Your Arena profile\n"
            "/profile &lt;handle&gt; - View a user's profile\n"
            "/bio &lt;text&gt; - Update your bio\n\n"
            "<b>Arena — Stats:</b>\n"
            "/shares - Share/token stats\n"
            "/holdings - Your holdings\n"
            "/earnings - Earnings breakdown\n"
            "/holders - Who holds your shares\n\n"
            "<b>Arena — Notifications:</b>\n"
            "/notifs - Recent notifications\n"
            "/notifs_clear - Mark all as seen\n\n"
            "<b>Arena — Chat:</b>\n"
            "/conversations - List chats\n"
            "/dm &lt;user_id&gt; &lt;text&gt; - Send a DM\n\n"
            "<b>Arena — Communities:</b>\n"
            "/communities - Top communities\n"
            "/search_community &lt;query&gt; - Search communities"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        self.brain.reset_conversation(self.owner_id)
        await update.message.reply_text("Memory cleared.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return

        lines = [
            "<b>Bot Status</b>\n",
            f"Model: <code>{escape(self.brain.model_name)}</code>",
            f"Device: <code>{self.brain.device}</code>",
            f"Max tokens: {self.brain.max_tokens}",
            f"Temperature: {self.brain.temperature}",
            f"Context window: {self.brain.max_context}",
        ]

        if self.arena and self.arena.configured:
            lines.append(f"\nArena: <code>{escape(self.arena.handle or self.arena.agent_id)}</code>")
        else:
            lines.append("\nArena: not configured")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    # ================================================================
    # INTENT DETECTION — route natural language to Arena actions
    # ================================================================

    # Each entry: (intent_name, list_of_regex_patterns)
    _INTENT_PATTERNS = [
        # --- Posts ---
        ("post", [
            r"(?:create|make|write|draft|compose|do|send)\s+(?:a\s+)?(?:post|thread|tweet)",
            r"post\s+(?:on|to|about|this)",
            r"(?:put|share)\s+(?:this\s+)?(?:on|to)\s+arena",
            r"arena\s+post",
        ]),
        # --- Feeds ---
        ("feed", [
            r"(?:show|check|get|view|open|see|what'?s?\s+(?:on|in))\s+(?:my\s+)?feed",
            r"my\s+feed",
            r"(?:show|check)\s+(?:my\s+)?arena\s+feed",
        ]),
        ("trending", [
            r"(?:show|check|get|view|what'?s?)\s+trending",
            r"trending\s+(?:feed|posts?|on\s+arena)",
        ]),
        # --- Profile ---
        ("me", [
            r"(?:show|check|get|view|see)\s+my\s+(?:arena\s+)?profile",
            r"my\s+(?:arena\s+)?profile",
            r"who\s+am\s+i\s+on\s+arena",
        ]),
        # --- Social ---
        ("followers", [
            r"(?:show|check|get|view|see|list|who\s+are)\s+(?:my\s+)?followers",
            r"my\s+followers",
            r"who\s+follows\s+me",
        ]),
        ("following", [
            r"(?:show|check|get|view|see|list)\s+(?:who\s+(?:i|am)\s+follow|(?:my\s+)?following)",
            r"who\s+(?:do\s+)?i\s+follow",
            r"my\s+following",
        ]),
        ("follow", [
            r"follow\s+(?:user\s+)?(@?\w+)",
            r"follow\s+(?:them|this\s+user|that\s+user)",
        ]),
        ("unfollow", [
            r"unfollow\s+(?:user\s+)?(@?\w+)",
            r"unfollow\s+(?:them|this\s+user|that\s+user)",
        ]),
        ("search_users", [
            r"(?:search|find|look\s+(?:up|for))\s+(?:user|people|person|account)s?\s+(.+)",
            r"(?:search|find)\s+(?:on\s+arena\s+)?(?:for\s+)?(@?\w+)",
        ]),
        # --- Notifications ---
        ("notifications", [
            r"(?:show|check|get|view|see|any)\s+(?:my\s+)?notif(?:ication)?s?",
            r"my\s+notif(?:ication)?s?",
            r"do\s+i\s+have\s+(?:any\s+)?notif(?:ication)?s?",
            r"(?:what|any)\s+(?:new\s+)?notif(?:ication)?s?",
        ]),
        ("clear_notifications", [
            r"(?:clear|mark|dismiss|read)\s+(?:all\s+)?notif(?:ication)?s?(?:\s+(?:as\s+)?(?:seen|read))?",
        ]),
        # --- Stats / Financial ---
        ("shares", [
            r"(?:show|check|get|view|see)\s+(?:my\s+)?(?:share|token)\s*(?:stats?|info)?",
            r"my\s+(?:share|token)\s*stats?",
            r"(?:how\s+are|what\s+are)\s+my\s+shares?\s+(?:doing|at|worth)",
        ]),
        ("holdings", [
            r"(?:show|check|get|view|see)\s+(?:my\s+)?holdings?",
            r"my\s+holdings?",
            r"(?:what|which)\s+(?:shares?\s+)?(?:do\s+)?i\s+(?:hold|own)",
            r"my\s+portfolio",
        ]),
        ("earnings", [
            r"(?:show|check|get|view|see)\s+(?:my\s+)?earnings?",
            r"my\s+earnings?",
            r"how\s+much\s+(?:have\s+i|did\s+i)\s+(?:earn|made?)",
        ]),
        ("holders", [
            r"(?:show|check|get|view|see|who)\s+(?:are\s+)?(?:my\s+)?(?:share\s*)?holders?",
            r"who\s+(?:holds?|owns?|bought)\s+my\s+shares?",
        ]),
        # --- Chat ---
        ("conversations", [
            r"(?:show|check|get|view|see|list|open)\s+(?:my\s+)?(?:chat|conversation|message|dm)s?",
            r"my\s+(?:chat|conversation|dm)s?",
        ]),
        # --- Communities ---
        ("communities", [
            r"(?:show|check|get|view|see|list|browse)\s+(?:top\s+)?communit(?:y|ies)",
            r"(?:top|popular|trending)\s+communit(?:y|ies)",
        ]),
        # --- Like ---
        ("like", [
            r"like\s+(?:that|this|the)\s+(?:post|thread)",
            r"like\s+(?:post|thread)\s+(\S+)",
        ]),
        # --- Repost ---
        ("repost", [
            r"(?:repost|reshare|share)\s+(?:that|this|the)\s+(?:post|thread)",
            r"(?:repost|reshare)\s+(?:post|thread)\s+(\S+)",
        ]),
    ]

    def _detect_arena_intent(self, text: str) -> tuple[str | None, str]:
        """Detect if a message is requesting an Arena action.

        Returns:
            (intent, extra) — intent name or None, and any extracted argument.
        """
        lower = text.lower().strip()

        for intent_name, patterns in self._INTENT_PATTERNS:
            for pattern in patterns:
                match = re.search(pattern, lower)
                if match:
                    # Try to extract a captured group as the argument
                    extra = match.group(1) if match.lastindex else text
                    return intent_name, extra

        return None, text

    # ================================================================
    # MESSAGE HANDLER — LLM inference + intent routing (owner-only)
    # ================================================================

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        if not text:
            return

        if self._is_rate_limited(update.effective_user.id):
            await update.message.reply_text("Slow down — too many messages. Try again in a moment.")
            return

        if len(text) > MAX_INPUT_LENGTH:
            await update.message.reply_text(
                f"Message too long ({len(text)} chars). Please keep it under {MAX_INPUT_LENGTH}."
            )
            return

        # Show typing while generating
        await update.message.chat.send_action("typing")

        # Try to detect an Arena intent
        if self.arena and self.arena.configured:
            intent, extra = self._detect_arena_intent(text)
            handled = await self._dispatch_intent(update, intent, extra, text)
            if handled:
                return

        # Regular LLM conversation
        try:
            response = await asyncio.to_thread(
                self.brain.think, text, user_id=self.owner_id
            )
        except Exception as e:
            logger.error("LLM inference error: %s", e)
            await update.message.reply_text("Something went wrong during inference. Check logs.")
            return

        await send_long(update, response)

    async def _dispatch_intent(self, update: Update, intent: str | None, extra: str, original: str) -> bool:
        """Dispatch a detected intent to the right Arena action. Returns True if handled."""
        if intent is None:
            return False

        # --- Post: generate content via LLM then post ---
        if intent == "post":
            await self._handle_arena_post_intent(update, original, extra)
            return True

        # --- Feeds ---
        if intent == "feed":
            feed = await asyncio.to_thread(self.arena.get_my_feed)
            await self._display_feed(update, feed, "Your Feed")
            return True

        if intent == "trending":
            feed = await asyncio.to_thread(self.arena.get_trending_feed)
            await self._display_feed(update, feed, "Trending")
            return True

        # --- Profile ---
        if intent == "me":
            profile = await asyncio.to_thread(self.arena.get_me)
            if not profile:
                await update.message.reply_text("Could not load your Arena profile.")
                return True
            lines = ["<b>Your Arena Profile</b>\n"]
            if isinstance(profile, dict):
                for key in ["handle", "username", "bio", "followersCount", "followingCount", "sharesCount"]:
                    if key in profile:
                        lines.append(f"{key}: <code>{escape(str(profile[key]))}</code>")
            else:
                lines.append(escape(str(profile)))
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        # --- Social ---
        if intent == "followers":
            data = await asyncio.to_thread(self.arena.get_followers)
            await self._display_user_list(update, data, "Your Followers")
            return True

        if intent == "following":
            data = await asyncio.to_thread(self.arena.get_following)
            await self._display_user_list(update, data, "Following")
            return True

        if intent == "follow":
            result = await asyncio.to_thread(self.arena.follow_user, extra)
            await update.message.reply_text("Followed." if result else "Failed to follow.")
            return True

        if intent == "unfollow":
            result = await asyncio.to_thread(self.arena.unfollow_user, extra)
            await update.message.reply_text("Unfollowed." if result else "Failed to unfollow.")
            return True

        if intent == "search_users":
            data = await asyncio.to_thread(self.arena.search_users, extra)
            await self._display_user_list(update, data, f"Search: {escape(extra)}")
            return True

        # --- Notifications ---
        if intent == "notifications":
            data = await asyncio.to_thread(self.arena.get_notifications)
            if not data:
                await update.message.reply_text("No notifications.")
                return True
            lines = ["<b>Notifications</b>\n"]
            if isinstance(data, list):
                for item in data[:15]:
                    if isinstance(item, dict):
                        ntype = item.get("type", "")
                        actor = item.get("actorHandle", item.get("actor", "?"))
                        ntxt = item.get("text", item.get("content", ""))[:80]
                        lines.append(f"[{escape(str(ntype))}] @{escape(str(actor))}: {escape(ntxt)}")
                    else:
                        lines.append(escape(str(item))[:100])
            elif isinstance(data, dict):
                for k, v in data.items():
                    lines.append(f"{escape(str(k))}: {escape(str(v))}")
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        if intent == "clear_notifications":
            result = await asyncio.to_thread(self.arena.mark_notifications_seen)
            await update.message.reply_text(
                "Notifications marked as seen." if result is not None else "Failed."
            )
            return True

        # --- Stats ---
        if intent == "shares":
            stats = await asyncio.to_thread(self.arena.get_share_stats)
            if not stats:
                await update.message.reply_text("Could not load share stats.")
                return True
            lines = ["<b>Share Stats</b>\n"]
            if isinstance(stats, dict):
                for k, v in stats.items():
                    lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
            else:
                lines.append(escape(str(stats)))
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        if intent == "holdings":
            data = await asyncio.to_thread(self.arena.get_holdings)
            if not data:
                await update.message.reply_text("Could not load holdings.")
                return True
            lines = ["<b>Holdings</b>\n"]
            if isinstance(data, list):
                for item in data[:20]:
                    if isinstance(item, dict):
                        name = item.get("handle", item.get("username", "?"))
                        amount = item.get("amount", item.get("shares", "?"))
                        lines.append(f"@{escape(str(name))}: {escape(str(amount))}")
                    else:
                        lines.append(escape(str(item)))
            elif isinstance(data, dict):
                for k, v in data.items():
                    lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        if intent == "earnings":
            data = await asyncio.to_thread(self.arena.get_earnings)
            if not data:
                await update.message.reply_text("Could not load earnings.")
                return True
            lines = ["<b>Earnings</b>\n"]
            if isinstance(data, dict):
                for k, v in data.items():
                    lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
            else:
                lines.append(escape(str(data)))
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        if intent == "holders":
            data = await asyncio.to_thread(self.arena.get_share_holders)
            await self._display_user_list(update, data, "Your Share Holders")
            return True

        # --- Chat ---
        if intent == "conversations":
            data = await asyncio.to_thread(self.arena.get_conversations)
            if not data:
                await update.message.reply_text("No conversations.")
                return True
            lines = ["<b>Conversations</b>\n"]
            if isinstance(data, list):
                for conv in data[:15]:
                    if isinstance(conv, dict):
                        cid = conv.get("id", conv.get("conversationId", "?"))
                        name = conv.get("name", conv.get("handle", "?"))
                        lines.append(f"<code>{escape(str(cid))}</code> — {escape(str(name))}")
                    else:
                        lines.append(escape(str(conv))[:100])
            else:
                lines.append(escape(str(data)))
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        # --- Communities ---
        if intent == "communities":
            data = await asyncio.to_thread(self.arena.get_top_communities)
            if not data:
                await update.message.reply_text("Could not load communities.")
                return True
            lines = ["<b>Top Communities</b>\n"]
            if isinstance(data, list):
                for c in data[:15]:
                    if isinstance(c, dict):
                        name = c.get("name", "?")
                        cid = c.get("id", "?")
                        members = c.get("membersCount", "?")
                        lines.append(f"{escape(str(name))} (id: <code>{escape(str(cid))}</code>, members: {escape(str(members))})")
                    else:
                        lines.append(escape(str(c))[:100])
            else:
                lines.append(escape(str(data)))
            await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)
            return True

        # --- Like / Repost (need a thread ID from context) ---
        if intent == "like":
            # extra might be a thread ID if captured
            if extra and extra != original:
                result = await asyncio.to_thread(self.arena.like_thread, extra)
                await update.message.reply_text("Liked." if result else "Failed to like.")
            else:
                await update.message.reply_text("Which thread? Use /like <thread_id>")
            return True

        if intent == "repost":
            if extra and extra != original:
                result = await asyncio.to_thread(self.arena.repost, extra)
                await update.message.reply_text("Reposted." if result else "Failed to repost.")
            else:
                await update.message.reply_text("Which thread? Use /repost <thread_id>")
            return True

        return False

    # Internal user ID for post generation — avoids polluting the owner's conversation
    _INTERNAL_POST_USER_ID = -1

    async def _handle_arena_post_intent(self, update: Update, original_text: str, topic: str):
        """Handle natural language post request: generate content via LLM, then post to Arena."""
        # Extract topic from the message
        lower = topic.lower()
        # Clean up topic — remove arena/post keywords
        for noise in ["arena", "post", "thread", "tweet", "on", "to", "a", "create", "make", "write"]:
            lower = re.sub(rf"\b{noise}\b", "", lower)
        clean_topic = lower.strip()
        if not clean_topic or len(clean_topic) < 3:
            clean_topic = topic  # Fall back to full text

        prompt = (
            f"Write a short Arena post about: {clean_topic}\n\n"
            "Sound like a real person, not a chatbot. Under 280 characters. "
            "No hashtags, no bold, no emojis, no markdown — just natural text "
            "like you'd actually say it. Nothing promoting alcohol, gambling, "
            "explicit content, fraud, or anything haram."
        )

        try:
            # Use a separate internal user_id so the generation prompt
            # doesn't pollute the owner's real conversation history.
            content = await asyncio.to_thread(
                self.brain.think, prompt, user_id=self._INTERNAL_POST_USER_ID
            )
            # Clear the internal conversation so it doesn't accumulate
            self.brain.reset_conversation(self._INTERNAL_POST_USER_ID)
        except Exception as e:
            logger.error("LLM error generating post: %s", e)
            await update.message.reply_text("Failed to generate post content.")
            return

        if not content or len(content.strip()) < 3:
            await update.message.reply_text("Could not generate post content.")
            return

        content = content.strip()

        # Post to Arena
        result = await asyncio.to_thread(self.arena.create_thread, f"<p>{content}</p>")

        if result:
            msg = f"Posted to Arena:\n\n{content}"
            await send_long(update, msg)
        else:
            msg = f"Generated but failed to post:\n\n{content}\n\nTry again with /post"
            await send_long(update, msg)

    # ================================================================
    # ARENA — POSTS
    # ================================================================

    async def cmd_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create a post. Usage: /post <content>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        text = self._extract_args(update)
        if not text:
            await update.message.reply_text("Usage: /post &lt;content&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.create_thread, f"<p>{text}</p>")
        if result:
            await update.message.reply_text("Posted to Arena.")
        else:
            await update.message.reply_text("Failed to post.")

    async def cmd_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reply to a thread. Usage: /reply <thread_id> <content>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        parts = self._extract_args(update)
        if not parts or " " not in parts:
            await update.message.reply_text("Usage: /reply &lt;thread_id&gt; &lt;content&gt;", parse_mode=ParseMode.HTML)
            return

        thread_id, content = parts.split(" ", 1)
        result = await asyncio.to_thread(self.arena.reply_to_thread, thread_id, f"<p>{content}</p>")
        if result:
            await update.message.reply_text("Reply posted.")
        else:
            await update.message.reply_text("Failed to reply.")

    async def cmd_delete_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a post. Usage: /delete_post <thread_id>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        thread_id = self._extract_args(update)
        if not thread_id:
            await update.message.reply_text("Usage: /delete_post &lt;thread_id&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.delete_thread, thread_id)
        if result:
            await update.message.reply_text("Post deleted.")
        else:
            await update.message.reply_text("Failed to delete.")

    async def cmd_like(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Like a thread. Usage: /like <thread_id>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        thread_id = self._extract_args(update)
        if not thread_id:
            await update.message.reply_text("Usage: /like &lt;thread_id&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.like_thread, thread_id)
        if result:
            await update.message.reply_text("Liked.")
        else:
            await update.message.reply_text("Failed to like.")

    async def cmd_repost(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Repost a thread. Usage: /repost <thread_id>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        thread_id = self._extract_args(update)
        if not thread_id:
            await update.message.reply_text("Usage: /repost &lt;thread_id&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.repost, thread_id)
        if result:
            await update.message.reply_text("Reposted.")
        else:
            await update.message.reply_text("Failed to repost.")

    async def cmd_quote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quote-repost. Usage: /quote <thread_id> <content>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        parts = self._extract_args(update)
        if not parts or " " not in parts:
            await update.message.reply_text("Usage: /quote &lt;thread_id&gt; &lt;content&gt;", parse_mode=ParseMode.HTML)
            return

        thread_id, content = parts.split(" ", 1)
        result = await asyncio.to_thread(self.arena.quote_repost, thread_id, f"<p>{content}</p>")
        if result:
            await update.message.reply_text("Quote posted.")
        else:
            await update.message.reply_text("Failed to quote.")

    # ================================================================
    # ARENA — FEEDS
    # ================================================================

    async def cmd_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View your Arena feed."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        feed = await asyncio.to_thread(self.arena.get_my_feed)
        await self._display_feed(update, feed, "Your Feed")

    async def cmd_trending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View trending feed."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        feed = await asyncio.to_thread(self.arena.get_trending_feed)
        await self._display_feed(update, feed, "Trending")

    async def cmd_userfeed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View a user's posts. Usage: /userfeed <handle>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        handle = self._extract_args(update)
        if not handle:
            await update.message.reply_text("Usage: /userfeed &lt;handle&gt;", parse_mode=ParseMode.HTML)
            return

        feed = await asyncio.to_thread(self.arena.get_user_feed, handle)
        await self._display_feed(update, feed, f"Posts by @{escape(handle)}")

    # ================================================================
    # ARENA — SOCIAL
    # ================================================================

    async def cmd_follow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Follow a user. Usage: /follow <user_id>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        user_id = self._extract_args(update)
        if not user_id:
            await update.message.reply_text("Usage: /follow &lt;user_id&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.follow_user, user_id)
        if result:
            await update.message.reply_text("Followed.")
        else:
            await update.message.reply_text("Failed to follow.")

    async def cmd_unfollow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unfollow a user. Usage: /unfollow <user_id>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        user_id = self._extract_args(update)
        if not user_id:
            await update.message.reply_text("Usage: /unfollow &lt;user_id&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.unfollow_user, user_id)
        if result:
            await update.message.reply_text("Unfollowed.")
        else:
            await update.message.reply_text("Failed to unfollow.")

    async def cmd_followers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View your followers."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_followers)
        await self._display_user_list(update, data, "Your Followers")

    async def cmd_following(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View who you follow."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_following)
        await self._display_user_list(update, data, "Following")

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search users. Usage: /search <query>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        query = self._extract_args(update)
        if not query:
            await update.message.reply_text("Usage: /search &lt;query&gt;", parse_mode=ParseMode.HTML)
            return

        data = await asyncio.to_thread(self.arena.search_users, query)
        await self._display_user_list(update, data, f"Search: {escape(query)}")

    # ================================================================
    # ARENA — PROFILE
    # ================================================================

    async def cmd_me(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View your Arena profile."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        profile = await asyncio.to_thread(self.arena.get_me)
        if not profile:
            await update.message.reply_text("Could not load profile.")
            return

        lines = ["<b>Your Arena Profile</b>\n"]
        if isinstance(profile, dict):
            for key in ["handle", "username", "bio", "followersCount", "followingCount", "sharesCount"]:
                if key in profile:
                    lines.append(f"{key}: <code>{escape(str(profile[key]))}</code>")
        else:
            lines.append(escape(str(profile)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View a user's profile. Usage: /profile <handle>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        handle = self._extract_args(update)
        if not handle:
            await update.message.reply_text("Usage: /profile &lt;handle&gt;", parse_mode=ParseMode.HTML)
            return

        profile = await asyncio.to_thread(self.arena.get_user_by_handle, handle)
        if not profile:
            await update.message.reply_text(f"User @{escape(handle)} not found.", parse_mode=ParseMode.HTML)
            return

        lines = [f"<b>@{escape(handle)}</b>\n"]
        if isinstance(profile, dict):
            for key in ["username", "bio", "followersCount", "followingCount", "sharesCount", "id"]:
                if key in profile:
                    lines.append(f"{key}: <code>{escape(str(profile[key]))}</code>")
        else:
            lines.append(escape(str(profile)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Update your bio. Usage: /bio <text>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        bio_text = self._extract_args(update)
        if not bio_text:
            await update.message.reply_text("Usage: /bio &lt;text&gt;", parse_mode=ParseMode.HTML)
            return

        result = await asyncio.to_thread(self.arena.update_profile, bio=bio_text)
        if result:
            await update.message.reply_text("Bio updated.")
        else:
            await update.message.reply_text("Failed to update bio.")

    # ================================================================
    # ARENA — STATS / FINANCIAL
    # ================================================================

    async def cmd_shares(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View share/token stats."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        stats = await asyncio.to_thread(self.arena.get_share_stats)
        if not stats:
            await update.message.reply_text("Could not load share stats.")
            return

        lines = ["<b>Share Stats</b>\n"]
        if isinstance(stats, dict):
            for k, v in stats.items():
                lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
        else:
            lines.append(escape(str(stats)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_holdings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View your holdings."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_holdings)
        if not data:
            await update.message.reply_text("Could not load holdings.")
            return

        lines = ["<b>Holdings</b>\n"]
        if isinstance(data, list):
            for item in data[:20]:
                if isinstance(item, dict):
                    name = item.get("handle", item.get("username", "?"))
                    amount = item.get("amount", item.get("shares", "?"))
                    lines.append(f"@{escape(str(name))}: {escape(str(amount))}")
                else:
                    lines.append(escape(str(item)))
        elif isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
        else:
            lines.append(escape(str(data)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_earnings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View earnings breakdown."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_earnings)
        if not data:
            await update.message.reply_text("Could not load earnings.")
            return

        lines = ["<b>Earnings</b>\n"]
        if isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
        else:
            lines.append(escape(str(data)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_holders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View who holds your shares."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_share_holders)
        await self._display_user_list(update, data, "Your Share Holders")

    # ================================================================
    # ARENA — NOTIFICATIONS
    # ================================================================

    async def cmd_notifs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View recent notifications."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_notifications)
        if not data:
            await update.message.reply_text("No notifications.")
            return

        lines = ["<b>Notifications</b>\n"]
        if isinstance(data, list):
            for item in data[:15]:
                if isinstance(item, dict):
                    ntype = item.get("type", "")
                    actor = item.get("actorHandle", item.get("actor", "?"))
                    text = item.get("text", item.get("content", ""))[:80]
                    lines.append(f"[{escape(str(ntype))}] @{escape(str(actor))}: {escape(text)}")
                else:
                    lines.append(escape(str(item))[:100])
        elif isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"{escape(str(k))}: {escape(str(v))}")
        else:
            lines.append(escape(str(data)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_notifs_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark all notifications as seen."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        result = await asyncio.to_thread(self.arena.mark_notifications_seen)
        if result is not None:
            await update.message.reply_text("Notifications marked as seen.")
        else:
            await update.message.reply_text("Failed to clear notifications.")

    # ================================================================
    # ARENA — CHAT / DM
    # ================================================================

    async def cmd_conversations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List your Arena chat conversations."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_conversations)
        if not data:
            await update.message.reply_text("No conversations.")
            return

        lines = ["<b>Conversations</b>\n"]
        if isinstance(data, list):
            for conv in data[:15]:
                if isinstance(conv, dict):
                    cid = conv.get("id", conv.get("conversationId", "?"))
                    name = conv.get("name", conv.get("handle", "?"))
                    lines.append(f"<code>{escape(str(cid))}</code> — {escape(str(name))}")
                else:
                    lines.append(escape(str(conv))[:100])
        else:
            lines.append(escape(str(data)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a DM. Usage: /dm <user_id> <message>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        parts = self._extract_args(update)
        if not parts or " " not in parts:
            await update.message.reply_text("Usage: /dm &lt;user_id&gt; &lt;message&gt;", parse_mode=ParseMode.HTML)
            return

        user_id, message = parts.split(" ", 1)

        # Get or create conversation with this user
        conv = await asyncio.to_thread(self.arena.get_or_create_conversation, user_id)
        if not conv:
            await update.message.reply_text("Could not find/create conversation with that user.")
            return

        conv_id = conv.get("id", conv.get("conversationId")) if isinstance(conv, dict) else str(conv)
        if not conv_id:
            await update.message.reply_text("Could not get conversation ID.")
            return

        result = await asyncio.to_thread(self.arena.send_message, str(conv_id), message)
        if result:
            await update.message.reply_text("DM sent.")
        else:
            await update.message.reply_text("Failed to send DM.")

    # ================================================================
    # ARENA — COMMUNITIES
    # ================================================================

    async def cmd_communities(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View top communities."""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        data = await asyncio.to_thread(self.arena.get_top_communities)
        if not data:
            await update.message.reply_text("Could not load communities.")
            return

        lines = ["<b>Top Communities</b>\n"]
        if isinstance(data, list):
            for c in data[:15]:
                if isinstance(c, dict):
                    name = c.get("name", "?")
                    cid = c.get("id", "?")
                    members = c.get("membersCount", "?")
                    lines.append(f"{escape(str(name))} (id: <code>{escape(str(cid))}</code>, members: {escape(str(members))})")
                else:
                    lines.append(escape(str(c))[:100])
        else:
            lines.append(escape(str(data)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_search_community(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search communities. Usage: /search_community <query>"""
        if not self._is_owner(update):
            return
        if not await self._require_arena(update):
            return

        query = self._extract_args(update)
        if not query:
            await update.message.reply_text("Usage: /search_community &lt;query&gt;", parse_mode=ParseMode.HTML)
            return

        data = await asyncio.to_thread(self.arena.search_communities, query)
        if not data:
            await update.message.reply_text("No communities found.")
            return

        lines = [f"<b>Communities: {escape(query)}</b>\n"]
        if isinstance(data, list):
            for c in data[:15]:
                if isinstance(c, dict):
                    name = c.get("name", "?")
                    cid = c.get("id", "?")
                    lines.append(f"{escape(str(name))} (id: <code>{escape(str(cid))}</code>)")
                else:
                    lines.append(escape(str(c))[:100])
        else:
            lines.append(escape(str(data)))

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    # ================================================================
    # HELPERS
    # ================================================================

    def _extract_args(self, update: Update) -> str:
        """Extract arguments after the command name, handling @botname suffix."""
        if not update.message or not update.message.text:
            return ""
        text = update.message.text
        # Split on first whitespace: ["/command@botname", "args..."]
        parts = text.split(None, 1)
        return parts[1].strip() if len(parts) > 1 else ""

    async def _require_arena(self, update: Update) -> bool:
        """Check if Arena is configured. Sends error message if not."""
        if self.arena and self.arena.configured:
            return True
        await update.message.reply_text("Arena not configured. Set ARENA_API_KEY and ARENA_AGENT_ID.")
        return False

    async def _display_feed(self, update: Update, feed, title: str):
        """Format and display a feed response."""
        if not feed:
            await update.message.reply_text(f"{title}: empty or failed to load.")
            return

        lines = [f"<b>{escape(title)}</b>\n"]

        items = feed if isinstance(feed, list) else (feed.get("items", feed.get("threads", [])) if isinstance(feed, dict) else [])

        if not items:
            if isinstance(feed, dict):
                lines.append(escape(str(feed))[:500])
            else:
                lines.append("No items.")
        else:
            for item in items[:10]:
                if isinstance(item, dict):
                    author = item.get("handle", item.get("authorHandle", item.get("author", "?")))
                    content = item.get("content", item.get("text", ""))
                    # Strip HTML tags for display
                    content = re.sub(r"<[^>]+>", "", str(content))[:120]
                    tid = item.get("id", item.get("threadId", ""))
                    line = f"@{escape(str(author))}: {escape(content)}"
                    if tid:
                        line += f" [<code>{escape(str(tid))}</code>]"
                    lines.append(line)
                else:
                    lines.append(escape(str(item))[:120])

        await send_long(update, "\n\n".join(lines), parse_mode=ParseMode.HTML)

    async def _display_user_list(self, update: Update, data, title: str):
        """Format and display a list of users."""
        if not data:
            await update.message.reply_text(f"{title}: empty or failed to load.")
            return

        lines = [f"<b>{escape(title)}</b>\n"]

        items = data if isinstance(data, list) else (data.get("users", data.get("items", [])) if isinstance(data, dict) else [])

        if not items:
            if isinstance(data, dict):
                for k, v in list(data.items())[:10]:
                    lines.append(f"{escape(str(k))}: <code>{escape(str(v))}</code>")
            else:
                lines.append("No users.")
        else:
            for user in items[:20]:
                if isinstance(user, dict):
                    handle = user.get("handle", "?")
                    name = user.get("username", user.get("name", ""))
                    uid = user.get("id", "")
                    line = f"@{escape(str(handle))}"
                    if name:
                        line += f" ({escape(str(name))})"
                    if uid:
                        line += f" [<code>{escape(str(uid))}</code>]"
                    lines.append(line)
                else:
                    lines.append(escape(str(user))[:100])

        await send_long(update, "\n".join(lines), parse_mode=ParseMode.HTML)

    # ================================================================
    # GLOBAL ERROR HANDLER
    # ================================================================

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log errors and notify the owner via Telegram."""
        logger.error("Exception while handling an update:", exc_info=context.error)

        tb = traceback.format_exception(type(context.error), context.error, context.error.__traceback__)
        tb_text = "".join(tb)

        # Try to notify the owner
        if self.owner_id and context.bot:
            try:
                escaped_tb = escape(tb_text)
                msg = f"<b>Bot Error</b>\n\n<pre>{escaped_tb}</pre>"
                if len(msg) <= TG_MSG_LIMIT:
                    await context.bot.send_message(
                        chat_id=self.owner_id, text=msg, parse_mode=ParseMode.HTML,
                    )
                else:
                    # Too long for HTML — send as plain text truncated safely
                    plain = f"Bot Error\n\n{tb_text}"
                    await context.bot.send_message(
                        chat_id=self.owner_id, text=plain[:TG_MSG_LIMIT],
                    )
            except Exception:
                logger.error("Failed to send error notification to owner.")

    # ================================================================
    # APP SETUP
    # ================================================================

    async def post_init(self, application: Application):
        """Called after the application is initialized — sets bot commands."""
        commands = [
            BotCommand("start", "Welcome message"),
            BotCommand("help", "Full command list"),
            BotCommand("reset", "Clear conversation memory"),
            BotCommand("status", "Bot & model stats"),
            BotCommand("post", "Create an Arena post"),
            BotCommand("reply", "Reply to a thread"),
            BotCommand("feed", "Your Arena feed"),
            BotCommand("trending", "Trending feed"),
            BotCommand("me", "Your Arena profile"),
            BotCommand("shares", "Share/token stats"),
            BotCommand("follow", "Follow a user"),
            BotCommand("search", "Search users"),
            BotCommand("notifs", "Notifications"),
            BotCommand("dm", "Send a DM"),
            BotCommand("communities", "Top communities"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered with Telegram.")

        # Log startup info
        me = await application.bot.get_me()
        logger.info("Bot started: @%s (id: %d)", me.username, me.id)
        logger.info("Owner ID: %d", self.owner_id)

        # Notify owner that bot is online
        if self.owner_id:
            try:
                await application.bot.send_message(
                    chat_id=self.owner_id,
                    text="<b>Bot online.</b> Model loaded and ready.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                logger.warning("Could not send startup notification to owner.")

    async def post_shutdown(self, application: Application):
        """Called during shutdown — cleanup."""
        logger.info("Bot shutting down.")

    def build_app(self) -> Application:
        if not self.bot_token:
            raise ValueError("No bot token. Set TELEGRAM_BOT_TOKEN env var on Railway.")

        app = (
            Application.builder()
            .token(self.bot_token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )

        # --- General commands ---
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("reset", self.cmd_reset))
        app.add_handler(CommandHandler("status", self.cmd_status))

        # --- Arena: Posts ---
        app.add_handler(CommandHandler("post", self.cmd_post))
        app.add_handler(CommandHandler("reply", self.cmd_reply))
        app.add_handler(CommandHandler("delete_post", self.cmd_delete_post))
        app.add_handler(CommandHandler("like", self.cmd_like))
        app.add_handler(CommandHandler("repost", self.cmd_repost))
        app.add_handler(CommandHandler("quote", self.cmd_quote))

        # --- Arena: Feeds ---
        app.add_handler(CommandHandler("feed", self.cmd_feed))
        app.add_handler(CommandHandler("trending", self.cmd_trending))
        app.add_handler(CommandHandler("userfeed", self.cmd_userfeed))

        # --- Arena: Social ---
        app.add_handler(CommandHandler("follow", self.cmd_follow))
        app.add_handler(CommandHandler("unfollow", self.cmd_unfollow))
        app.add_handler(CommandHandler("followers", self.cmd_followers))
        app.add_handler(CommandHandler("following", self.cmd_following))
        app.add_handler(CommandHandler("search", self.cmd_search))

        # --- Arena: Profile ---
        app.add_handler(CommandHandler("me", self.cmd_me))
        app.add_handler(CommandHandler("profile", self.cmd_profile))
        app.add_handler(CommandHandler("bio", self.cmd_bio))

        # --- Arena: Stats ---
        app.add_handler(CommandHandler("shares", self.cmd_shares))
        app.add_handler(CommandHandler("holdings", self.cmd_holdings))
        app.add_handler(CommandHandler("earnings", self.cmd_earnings))
        app.add_handler(CommandHandler("holders", self.cmd_holders))

        # --- Arena: Notifications ---
        app.add_handler(CommandHandler("notifs", self.cmd_notifs))
        app.add_handler(CommandHandler("notifs_clear", self.cmd_notifs_clear))

        # --- Arena: Chat ---
        app.add_handler(CommandHandler("conversations", self.cmd_conversations))
        app.add_handler(CommandHandler("dm", self.cmd_dm))

        # --- Arena: Communities ---
        app.add_handler(CommandHandler("communities", self.cmd_communities))
        app.add_handler(CommandHandler("search_community", self.cmd_search_community))

        # --- Message handler (catches all non-command text) ---
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # --- Global error handler ---
        app.add_error_handler(self.error_handler)

        return app

    def run(self):
        app = self.build_app()
        logger.info("Telegram bot starting (polling mode)...")
        app.run_polling(drop_pending_updates=True)
