"""Arena social platform API client.

Base URL: https://api.starsarena.com
Auth: X-API-Key header
Docs: https://arena.social/agents

Rate limits:
    Write:  threads 10/hr, livestreams 1/hr, stages 1/hr, chat 90/hr
    Update: PUT/PATCH 10/hr each
    Delete: 5/hr
    Read:   GET 100/min
    Global: 1,000 req/hr combined
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.starsarena.com"


class ArenaClient:
    """Client for the Arena social platform agent API."""

    def __init__(self, config: dict):
        arena_cfg = config.get("arena", {})
        self.api_key = arena_cfg.get("api_key", "")
        self.agent_id = arena_cfg.get("agent_id", "")
        self.handle = arena_cfg.get("handle", "")
        self.wallet = arena_cfg.get("wallet", "")
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        })

    @property
    def configured(self) -> bool:
        """Check if the Arena client has credentials."""
        return bool(self.api_key and self.agent_id)

    def _request(self, method: str, path: str, **kwargs) -> dict | None:
        """Make an API request and return parsed JSON."""
        url = f"{BASE_URL}{path}"
        try:
            resp = self._session.request(method, url, timeout=15, **kwargs)
            data = resp.json()
            if not data.get("success"):
                error = data.get("error", "Unknown error")
                hint = data.get("hint", "")
                logger.warning("Arena API error on %s %s: %s %s", method, path, error, hint)
                return None
            return data.get("data", data)
        except requests.Timeout:
            logger.error("Arena API timeout: %s %s", method, path)
            return None
        except Exception as e:
            logger.error("Arena API error: %s %s — %s", method, path, e)
            return None

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("POST", path, json=json)

    def _put(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("PUT", path, json=json)

    def _delete(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("DELETE", path, json=json)

    # ---- User / Profile ----

    def get_me(self) -> dict | None:
        """Get the agent's own profile."""
        return self._get("/agents/user/me")

    def get_user_by_handle(self, handle: str) -> dict | None:
        """Get a user's profile by handle."""
        return self._get("/agents/user/handle", params={"handle": handle})

    def search_users(self, query: str) -> dict | None:
        """Search for users by handle or username."""
        return self._get("/agents/user/search", params={"query": query})

    def get_trending_users(self) -> dict | None:
        """Get trending/top users."""
        return self._get("/agents/user/top")

    # ---- Threads / Posts ----

    def create_thread(self, content: str, privacy: int = 0) -> dict | None:
        """Create a new post/thread.

        Args:
            content: HTML-formatted post content.
            privacy: 0=public, 1=followers only, 2=shareholders only.
        """
        return self._post("/agents/threads", json={
            "content": content,
            "privacy": privacy,
        })

    def reply_to_thread(self, thread_id: str, content: str) -> dict | None:
        """Reply to a thread.

        Args:
            thread_id: ID of the thread to reply to.
            content: HTML-formatted reply content.
        """
        return self._post("/agents/threads/answer", json={
            "threadId": thread_id,
            "content": content,
        })

    def like_thread(self, thread_id: str) -> dict | None:
        """Like/unlike a thread (toggles)."""
        return self._post("/agents/threads/like/unlike", json={
            "threadId": thread_id,
        })

    def get_my_feed(self, page: int = 1) -> dict | None:
        """Get the agent's feed."""
        return self._get("/agents/threads/feed/my", params={"page": page})

    # ---- Social / Follow ----

    def follow_user(self, user_id: str) -> dict | None:
        """Follow a user."""
        return self._post("/agents/follow/follow", json={
            "userId": user_id,
        })

    def get_followers(self, page: int = 1) -> dict | None:
        """Get the agent's followers."""
        return self._get("/agents/follow/followers/list", params={"page": page})

    def follow_community(self, community_id: str) -> dict | None:
        """Join/follow a community."""
        return self._post("/agents/follow/follow-community", json={
            "communityId": community_id,
        })

    # ---- Chat / Messaging ----

    def get_conversations(self) -> dict | None:
        """List the agent's chat conversations."""
        return self._get("/agents/chat/conversations")

    def send_message(self, conversation_id: str, content: str) -> dict | None:
        """Send a chat message.

        Args:
            conversation_id: ID of the conversation.
            content: Message text.
        """
        return self._post("/agents/chat/message", json={
            "conversationId": conversation_id,
            "content": content,
        })

    def react_to_message(self, message_id: str, emoji: str) -> dict | None:
        """React to a message with an emoji."""
        return self._post("/agents/chat/react", json={
            "messageId": message_id,
            "emoji": emoji,
        })

    # ---- Broadcast ----

    def create_stage(self, title: str) -> dict | None:
        """Create an audio room/stage."""
        return self._post("/agents/stages", json={
            "title": title,
        })

    def create_livestream(self, title: str) -> dict | None:
        """Create a video livestream."""
        return self._post("/agents/livestreams", json={
            "title": title,
        })

    def get_livestreams(self) -> dict | None:
        """Browse active livestreams."""
        return self._get("/agents/threads/get-livestreams")

    # ---- Shares / Financial ----

    def get_share_stats(self) -> dict | None:
        """Get the agent's share/token statistics."""
        return self._get("/agents/shares/stats")

    def get_holdings(self) -> dict | None:
        """Get the agent's portfolio/holdings."""
        return self._get("/agents/shares/holdings")

    def get_earnings(self) -> dict | None:
        """Get earnings breakdown."""
        return self._get("/agents/shares/earnings-breakdown")
