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
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.starsarena.com"

# Retry config for 429 rate limit responses
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]  # seconds


class ArenaClient:
    """Complete client for the Arena social platform agent API."""

    def __init__(self, config: dict):
        arena_cfg = config.get("arena", {})
        self.api_key = arena_cfg.get("api_key", "")
        self.agent_id = arena_cfg.get("agent_id", "")
        self.handle = arena_cfg.get("handle", "")
        self.wallet = arena_cfg.get("wallet", "")
        self.verification_code = arena_cfg.get("verification_code", "")
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "AtlasBot/1.0",
        })

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.agent_id)

    # ---- Core request layer with retry ----

    def _request(self, method: str, path: str, **kwargs) -> dict | None:
        """Make an API request with retry on 429 rate limits."""
        url = f"{BASE_URL}{path}"
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._session.request(method, url, timeout=15, **kwargs)

                # Rate limited — retry with backoff
                if resp.status_code == 429:
                    if attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 10
                        logger.warning(
                            "Arena 429 rate limited on %s %s, retry %d/%d in %ds",
                            method, path, attempt + 1, MAX_RETRIES, wait,
                        )
                        time.sleep(wait)
                        continue
                    logger.error("Arena 429 rate limited on %s %s, all retries exhausted", method, path)
                    return None

                # Server errors — retry
                if resp.status_code >= 500:
                    last_error = f"HTTP {resp.status_code}"
                    if attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 10
                        logger.warning(
                            "Arena %d on %s %s, retry %d/%d in %ds",
                            resp.status_code, method, path, attempt + 1, MAX_RETRIES, wait,
                        )
                        time.sleep(wait)
                        continue
                    break

                # Client errors (4xx except 429) — don't retry
                if resp.status_code >= 400:
                    logger.warning("Arena HTTP %d on %s %s", resp.status_code, method, path)
                    return None

                try:
                    data = resp.json()
                except (ValueError, requests.exceptions.JSONDecodeError):
                    logger.error("Arena non-JSON response on %s %s (HTTP %d)", method, path, resp.status_code)
                    return None

                if not data.get("success"):
                    error = data.get("error", "Unknown error")
                    hint = data.get("hint", "")
                    logger.warning("Arena API error on %s %s: %s %s", method, path, error, hint)
                    return None
                return data.get("data", data)

            except requests.Timeout:
                last_error = "timeout"
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 10
                    logger.warning("Arena timeout on %s %s, retry %d/%d", method, path, attempt + 1, MAX_RETRIES)
                    time.sleep(wait)
                    continue
            except requests.ConnectionError:
                last_error = "connection error"
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 10
                    logger.warning("Arena connection error on %s %s, retry %d/%d", method, path, attempt + 1, MAX_RETRIES)
                    time.sleep(wait)
                    continue
            except Exception as e:
                logger.error("Arena API error: %s %s — %s", method, path, e)
                return None

        logger.error("Arena API failed after %d retries: %s %s (%s)", MAX_RETRIES, method, path, last_error)
        return None

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("POST", path, json=json)

    def _put(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("PUT", path, json=json)

    def _patch(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("PATCH", path, json=json)

    def _delete(self, path: str, json: dict | None = None) -> dict | None:
        return self._request("DELETE", path, json=json)

    # ================================================================
    # USER / PROFILE
    # ================================================================

    def get_me(self) -> dict | None:
        """Get the agent's own profile."""
        return self._get("/agents/user/me")

    def get_user_by_handle(self, handle: str) -> dict | None:
        """Get a user's profile by handle."""
        return self._get("/agents/user/handle", params={"handle": handle})

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Get a user's profile by ID."""
        return self._get(f"/agents/user/{user_id}")

    def get_user_profile(self, handle: str) -> dict | None:
        """Get a user's full profile page data."""
        return self._get("/agents/user/profile", params={"handle": handle})

    def update_profile(self, **fields) -> dict | None:
        """Update the agent's profile.

        Supported fields: username, bio, profileImage, coverImage, etc.
        """
        if not fields:
            return None
        return self._patch("/agents/user/profile", json=fields)

    def search_users(self, query: str) -> dict | None:
        """Search for users by handle or username."""
        return self._get("/agents/user/search", params={"query": query})

    def get_trending_users(self) -> dict | None:
        """Get trending/top users."""
        return self._get("/agents/user/top")

    # ================================================================
    # THREADS / POSTS
    # ================================================================

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
        """Like a thread."""
        return self._post("/agents/threads/like/unlike", json={
            "threadId": thread_id,
        })

    def unlike_thread(self, thread_id: str) -> dict | None:
        """Unlike a thread (explicit unlike)."""
        return self._post("/agents/threads/unlike", json={
            "threadId": thread_id,
        })

    def repost(self, thread_id: str) -> dict | None:
        """Repost/share a thread."""
        return self._post("/agents/threads/repost", json={
            "threadId": thread_id,
        })

    def quote_repost(self, thread_id: str, content: str) -> dict | None:
        """Quote-repost a thread with commentary.

        Args:
            thread_id: ID of the thread to quote.
            content: HTML-formatted quote content.
        """
        return self._post("/agents/threads/quote", json={
            "threadId": thread_id,
            "content": content,
        })

    def delete_thread(self, thread_id: str) -> dict | None:
        """Delete a thread."""
        return self._delete("/agents/threads", json={
            "threadId": thread_id,
        })

    def get_thread(self, thread_id: str) -> dict | None:
        """Get a specific thread by ID."""
        return self._get(f"/agents/threads/{thread_id}")

    def get_thread_replies(self, thread_id: str, page: int = 1) -> dict | None:
        """Get replies to a thread."""
        return self._get(f"/agents/threads/{thread_id}/replies", params={"page": page})

    # ================================================================
    # FEEDS
    # ================================================================

    def get_my_feed(self, page: int = 1) -> dict | None:
        """Get the agent's personalized feed."""
        return self._get("/agents/threads/feed/my", params={"page": page})

    def get_trending_feed(self, page: int = 1) -> dict | None:
        """Get the trending/popular feed."""
        return self._get("/agents/threads/feed/trending", params={"page": page})

    def get_user_feed(self, handle: str, page: int = 1) -> dict | None:
        """Get a specific user's posts."""
        return self._get("/agents/threads/feed/user", params={"handle": handle, "page": page})

    def get_community_feed(self, community_id: str, page: int = 1) -> dict | None:
        """Get a community's feed."""
        return self._get("/agents/threads/feed/community", params={
            "communityId": community_id, "page": page,
        })

    # ================================================================
    # SOCIAL / FOLLOW
    # ================================================================

    def follow_user(self, user_id: str) -> dict | None:
        """Follow a user."""
        return self._post("/agents/follow/follow", json={
            "userId": user_id,
        })

    def unfollow_user(self, user_id: str) -> dict | None:
        """Unfollow a user."""
        return self._post("/agents/follow/unfollow", json={
            "userId": user_id,
        })

    def get_followers(self, page: int = 1) -> dict | None:
        """Get the agent's followers."""
        return self._get("/agents/follow/followers/list", params={"page": page})

    def get_following(self, page: int = 1) -> dict | None:
        """Get the list of users the agent follows."""
        return self._get("/agents/follow/following/list", params={"page": page})

    def follow_community(self, community_id: str) -> dict | None:
        """Join/follow a community."""
        return self._post("/agents/follow/follow-community", json={
            "communityId": community_id,
        })

    def unfollow_community(self, community_id: str) -> dict | None:
        """Leave/unfollow a community."""
        return self._post("/agents/follow/unfollow-community", json={
            "communityId": community_id,
        })

    # ================================================================
    # NOTIFICATIONS
    # ================================================================

    def get_notifications(self, page: int = 1) -> dict | None:
        """Get the agent's notifications."""
        return self._get("/agents/notifications", params={"page": page})

    def get_unseen_notifications_count(self) -> dict | None:
        """Get count of unseen notifications."""
        return self._get("/agents/notifications/unseen")

    def mark_notifications_seen(self) -> dict | None:
        """Mark all notifications as seen."""
        return self._post("/agents/notifications/seen")

    # ================================================================
    # CHAT / MESSAGING
    # ================================================================

    def get_conversations(self) -> dict | None:
        """List the agent's chat conversations."""
        return self._get("/agents/chat/conversations")

    def get_or_create_conversation(self, user_id: str) -> dict | None:
        """Get or create a 1-on-1 conversation with a user."""
        return self._get("/agents/chat/group-by-user", params={"userId": user_id})

    def get_messages(self, conversation_id: str, page: int = 1) -> dict | None:
        """Get messages in a conversation."""
        return self._get("/agents/chat/messages", params={
            "conversationId": conversation_id, "page": page,
        })

    def send_message(self, conversation_id: str, content: str) -> dict | None:
        """Send a chat message."""
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

    def unreact_to_message(self, message_id: str, emoji: str) -> dict | None:
        """Remove a reaction from a message."""
        return self._post("/agents/chat/unreact", json={
            "messageId": message_id,
            "emoji": emoji,
        })

    # ================================================================
    # STAGES (Audio Rooms)
    # ================================================================

    def create_stage(self, title: str) -> dict | None:
        """Create an audio room/stage."""
        return self._post("/agents/stages", json={
            "title": title,
        })

    def start_stage(self, stage_id: str) -> dict | None:
        """Start/go live on a stage."""
        return self._post("/agents/stages/start", json={
            "stageId": stage_id,
        })

    def edit_stage(self, stage_id: str, title: str) -> dict | None:
        """Edit a stage's title."""
        return self._put("/agents/stages", json={
            "stageId": stage_id,
            "title": title,
        })

    def end_stage(self, stage_id: str) -> dict | None:
        """End/close a stage."""
        return self._post("/agents/stages/end", json={
            "stageId": stage_id,
        })

    def delete_stage(self, stage_id: str) -> dict | None:
        """Delete a stage."""
        return self._delete("/agents/stages", json={
            "stageId": stage_id,
        })

    def join_stage(self, stage_id: str) -> dict | None:
        """Join a stage as a listener."""
        return self._post("/agents/stages/join", json={
            "stageId": stage_id,
        })

    def leave_stage(self, stage_id: str) -> dict | None:
        """Leave a stage."""
        return self._post("/agents/stages/leave", json={
            "stageId": stage_id,
        })

    def get_stage_info(self, stage_id: str) -> dict | None:
        """Get details about a stage."""
        return self._get(f"/agents/stages/{stage_id}")

    # ================================================================
    # LIVESTREAMS (Video)
    # ================================================================

    def create_livestream(self, title: str) -> dict | None:
        """Create a video livestream."""
        return self._post("/agents/livestreams", json={
            "title": title,
        })

    def generate_livestream_ingress(self, livestream_id: str) -> dict | None:
        """Generate RTMP ingress URL for streaming."""
        return self._post("/agents/livestreams/generate-ingress", json={
            "livestreamId": livestream_id,
        })

    def start_livestream(self, livestream_id: str) -> dict | None:
        """Start/go live on a livestream."""
        return self._post("/agents/livestreams/start", json={
            "livestreamId": livestream_id,
        })

    def edit_livestream(self, livestream_id: str, title: str) -> dict | None:
        """Edit a livestream's title."""
        return self._put("/agents/livestreams", json={
            "livestreamId": livestream_id,
            "title": title,
        })

    def end_livestream(self, livestream_id: str) -> dict | None:
        """End a livestream."""
        return self._post("/agents/livestreams/end", json={
            "livestreamId": livestream_id,
        })

    def get_livestreams(self) -> dict | None:
        """Browse active livestreams."""
        return self._get("/agents/threads/get-livestreams")

    # ================================================================
    # SHARES / FINANCIAL
    # ================================================================

    def get_share_stats(self) -> dict | None:
        """Get the agent's share/token statistics."""
        return self._get("/agents/shares/stats")

    def get_holdings(self) -> dict | None:
        """Get the agent's portfolio/holdings."""
        return self._get("/agents/shares/holdings")

    def get_earnings(self) -> dict | None:
        """Get earnings breakdown."""
        return self._get("/agents/shares/earnings-breakdown")

    def get_share_holders(self) -> dict | None:
        """Get list of users holding the agent's shares."""
        return self._get("/agents/shares/holders")

    def get_holder_addresses(self) -> dict | None:
        """Get wallet addresses of share holders."""
        return self._get("/agents/shares/holder-addresses")

    # ================================================================
    # COMMUNITIES
    # ================================================================

    def get_top_communities(self) -> dict | None:
        """Get top/trending communities."""
        return self._get("/agents/communities/top")

    def get_new_communities(self) -> dict | None:
        """Get newly created communities."""
        return self._get("/agents/communities/new")

    def search_communities(self, query: str) -> dict | None:
        """Search communities by name."""
        return self._get("/agents/communities/search", params={"query": query})
