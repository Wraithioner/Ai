/** Arena.social agent API — full integration. */

import https from "https";

const BASE = "https://api.starsarena.com";

function getKey(): string {
  return process.env.ARENA_API_KEY ?? "";
}

function api(
  method: string,
  path: string,
  body?: Record<string, any>
): Promise<{ status: number; data: any }> {
  const key = getKey();
  if (!key) return Promise.resolve({ status: 0, data: "ARENA_API_KEY not set. Add it in Railway env vars." });

  const url = new URL(path, BASE);
  const payload = body ? JSON.stringify(body) : undefined;

  return new Promise((resolve) => {
    const opts = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname + url.search,
      method: method.toUpperCase(),
      headers: {
        "X-API-Key": key,
        "Content-Type": "application/json",
        "User-Agent": "Atlas/0.1",
      } as Record<string, string>,
      timeout: 15_000,
    };

    if (payload) {
      opts.headers["Content-Length"] = Buffer.byteLength(payload).toString();
    }

    const req = https.request(opts, (res) => {
      let raw = "";
      res.setEncoding("utf-8");
      res.on("data", (chunk) => {
        raw += chunk;
        if (raw.length > 10_000) res.destroy();
      });
      res.on("end", () => {
        try {
          resolve({ status: res.statusCode ?? 0, data: JSON.parse(raw) });
        } catch {
          resolve({ status: res.statusCode ?? 0, data: raw.slice(0, 4000) });
        }
      });
    });

    req.on("error", (e) => resolve({ status: 0, data: `Error: ${e.message}` }));
    req.on("timeout", () => { req.destroy(); resolve({ status: 0, data: "Request timed out." }); });

    if (payload) req.write(payload);
    req.end();
  });
}

function fmt(obj: any): string {
  if (typeof obj === "string") return obj;
  return JSON.stringify(obj, null, 2).slice(0, 3800);
}

// ─── Agent Profile ────────────────────────────────────────

export async function registerAgent(
  name: string,
  handle: string,
  bio: string
): Promise<string> {
  const res = await api("POST", "/agents/register", {
    name,
    handle,
    bio,
    profilePicture: "",
  });
  if (res.status === 0) return fmt(res.data);
  if (res.data?.apiKey) {
    return `Agent registered!\nHandle: @${handle}\nAPI Key: ${res.data.apiKey}\n\nSAVE THIS KEY — it's shown only once!`;
  }
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function getProfile(): Promise<string> {
  const res = await api("GET", "/agents/user/me");
  if (res.status === 0) return fmt(res.data);
  const u = res.data;
  if (u?.name) {
    return [
      `Name: ${u.name}`,
      `Handle: @${u.handle ?? "unknown"}`,
      `Bio: ${u.bio ?? "none"}`,
      `Followers: ${u.followerCount ?? 0}`,
      `Following: ${u.followingCount ?? 0}`,
      `Share Price: ${u.sharePrice ?? "N/A"}`,
    ].join("\n");
  }
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function updateProfile(
  name?: string,
  bio?: string,
  picture?: string
): Promise<string> {
  const body: Record<string, string> = {};
  if (name) body.name = name;
  if (bio) body.bio = bio;
  if (picture) body.profilePicture = picture;
  const res = await api("PATCH", "/agents/user/profile", body);
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? "Profile updated." : `HTTP ${res.status}\n${fmt(res.data)}`;
}

// ─── Posts / Threads ──────────────────────────────────────

export async function createPost(content: string): Promise<string> {
  const res = await api("POST", "/agents/threads", { content });
  if (res.status === 0) return fmt(res.data);
  if (res.data?.id) return `Post created! ID: ${res.data.id}`;
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function replyToPost(postId: string, content: string): Promise<string> {
  const res = await api("POST", "/agents/threads/answer", {
    threadId: postId,
    content,
  });
  if (res.status === 0) return fmt(res.data);
  if (res.data?.id) return `Reply posted! ID: ${res.data.id}`;
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function quotePost(postId: string, content: string): Promise<string> {
  const res = await api("POST", "/agents/threads/quote", {
    threadId: postId,
    content,
  });
  if (res.status === 0) return fmt(res.data);
  if (res.data?.id) return `Quote posted! ID: ${res.data.id}`;
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function likePost(postId: string): Promise<string> {
  const res = await api("POST", "/agents/threads/like", { threadId: postId });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Liked post ${postId}.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function unlikePost(postId: string): Promise<string> {
  const res = await api("POST", "/agents/threads/unlike", { threadId: postId });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Unliked post ${postId}.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function repost(postId: string): Promise<string> {
  const res = await api("POST", "/agents/threads/repost", { threadId: postId });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Reposted ${postId}.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

// ─── Users / Social ───────────────────────────────────────

export async function searchUser(query: string): Promise<string> {
  const res = await api("GET", `/agents/user/search?query=${encodeURIComponent(query)}`);
  if (res.status === 0) return fmt(res.data);
  const users = Array.isArray(res.data) ? res.data : res.data?.users ?? [];
  if (users.length === 0) return `No users found for "${query}".`;
  return users
    .slice(0, 15)
    .map((u: any) => `@${u.handle ?? u.username ?? "?"} — ${u.name ?? ""}`)
    .join("\n");
}

export async function trending(page = 1): Promise<string> {
  const res = await api("GET", `/agents/user/top?page=${page}`);
  if (res.status === 0) return fmt(res.data);
  const users = Array.isArray(res.data) ? res.data : res.data?.users ?? [];
  if (users.length === 0) return "No trending users.";
  return users
    .slice(0, 15)
    .map((u: any, i: number) => `${(page - 1) * 15 + i + 1}. @${u.handle ?? "?"} — ${u.name ?? ""}`)
    .join("\n");
}

export async function getUserByHandle(handle: string): Promise<string> {
  const res = await api("GET", `/agents/user/handle?handle=${encodeURIComponent(handle)}`);
  if (res.status === 0) return fmt(res.data);
  const u = res.data;
  if (u?.name || u?.handle) {
    return [
      `Name: ${u.name ?? "?"}`,
      `Handle: @${u.handle ?? "?"}`,
      `Bio: ${u.bio ?? "none"}`,
      `Followers: ${u.followerCount ?? 0}`,
      `Share Price: ${u.sharePrice ?? "N/A"}`,
    ].join("\n");
  }
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function follow(handle: string): Promise<string> {
  const res = await api("POST", "/agents/follow/follow", { handle });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Followed @${handle}.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function unfollow(handle: string): Promise<string> {
  const res = await api("POST", "/agents/follow/unfollow", { handle });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Unfollowed @${handle}.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function getFollowers(handle: string): Promise<string> {
  const res = await api("GET", `/agents/follow/followers/list?handle=${encodeURIComponent(handle)}`);
  if (res.status === 0) return fmt(res.data);
  const users = Array.isArray(res.data) ? res.data : res.data?.followers ?? [];
  if (users.length === 0) return "No followers found.";
  return users
    .slice(0, 20)
    .map((u: any) => `@${u.handle ?? u.username ?? "?"}`)
    .join("\n");
}

// ─── Messaging / Chat ─────────────────────────────────────

export async function getConversations(): Promise<string> {
  const res = await api("GET", "/agents/chat/conversations");
  if (res.status === 0) return fmt(res.data);
  const convos = Array.isArray(res.data) ? res.data : res.data?.conversations ?? [];
  if (convos.length === 0) return "No conversations.";
  return convos
    .slice(0, 15)
    .map((c: any) => `${c.id ?? "?"} — ${c.otherUser?.handle ?? c.name ?? "unknown"}`)
    .join("\n");
}

export async function sendMessage(conversationId: string, content: string): Promise<string> {
  const res = await api("POST", "/agents/chat/message", {
    conversationId,
    content,
  });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 || res.status === 201
    ? `Message sent.`
    : `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function reactToMessage(messageId: string, emoji: string): Promise<string> {
  const res = await api("POST", "/agents/chat/react", { messageId, emoji });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Reacted ${emoji} to message.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

// ─── Live / Stages ────────────────────────────────────────

export async function createStage(title: string): Promise<string> {
  const res = await api("POST", "/agents/stages", { title });
  if (res.status === 0) return fmt(res.data);
  if (res.data?.id) return `Stage created! ID: ${res.data.id}\nTitle: ${title}`;
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function createLivestream(title: string): Promise<string> {
  const res = await api("POST", "/agents/livestreams", { title });
  if (res.status === 0) return fmt(res.data);
  if (res.data?.id) return `Livestream created! ID: ${res.data.id}\nTitle: ${title}`;
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function getStages(): Promise<string> {
  const res = await api("GET", "/agents/threads/get-stages");
  if (res.status === 0) return fmt(res.data);
  const stages = Array.isArray(res.data) ? res.data : res.data?.stages ?? [];
  if (stages.length === 0) return "No active stages.";
  return stages
    .slice(0, 10)
    .map((s: any) => `${s.id ?? "?"} — ${s.title ?? "untitled"}`)
    .join("\n");
}

export async function getLivestreams(): Promise<string> {
  const res = await api("GET", "/agents/threads/get-livestreams");
  if (res.status === 0) return fmt(res.data);
  const streams = Array.isArray(res.data) ? res.data : res.data?.livestreams ?? [];
  if (streams.length === 0) return "No active livestreams.";
  return streams
    .slice(0, 10)
    .map((s: any) => `${s.id ?? "?"} — ${s.title ?? "untitled"}`)
    .join("\n");
}

// ─── Shares / Economics ───────────────────────────────────

export async function shareStats(handle?: string): Promise<string> {
  const q = handle ? `?handle=${encodeURIComponent(handle)}` : "";
  const res = await api("GET", `/agents/shares/stats${q}`);
  if (res.status === 0) return fmt(res.data);
  const s = res.data;
  if (s?.price !== undefined || s?.sharePrice !== undefined) {
    return [
      `Price: ${s.price ?? s.sharePrice ?? "?"}`,
      `Holders: ${s.holders ?? s.holderCount ?? "?"}`,
      `Supply: ${s.supply ?? "?"}`,
      `Volume: ${s.volume ?? "?"}`,
    ].join("\n");
  }
  return `HTTP ${res.status}\n${fmt(res.data)}`;
}

export async function holdings(): Promise<string> {
  const res = await api("GET", "/agents/shares/holdings");
  if (res.status === 0) return fmt(res.data);
  const list = Array.isArray(res.data) ? res.data : res.data?.holdings ?? [];
  if (list.length === 0) return "No holdings.";
  return list
    .slice(0, 20)
    .map((h: any) => `@${h.handle ?? "?"} — ${h.amount ?? "?"} shares (${h.value ?? "?"})`)
    .join("\n");
}

export async function earnings(): Promise<string> {
  const res = await api("GET", "/agents/shares/earnings-breakdown");
  if (res.status === 0) return fmt(res.data);
  return fmt(res.data);
}

// ─── Communities ──────────────────────────────────────────

export async function topCommunities(): Promise<string> {
  const res = await api("GET", "/agents/communities/top");
  if (res.status === 0) return fmt(res.data);
  const comms = Array.isArray(res.data) ? res.data : res.data?.communities ?? [];
  if (comms.length === 0) return "No communities found.";
  return comms
    .slice(0, 15)
    .map((c: any) => `${c.name ?? "?"} — ${c.memberCount ?? "?"} members`)
    .join("\n");
}

export async function searchCommunity(query: string): Promise<string> {
  const res = await api("GET", `/agents/communities/search?query=${encodeURIComponent(query)}`);
  if (res.status === 0) return fmt(res.data);
  const comms = Array.isArray(res.data) ? res.data : res.data?.communities ?? [];
  if (comms.length === 0) return `No communities matching "${query}".`;
  return comms
    .slice(0, 15)
    .map((c: any) => `${c.name ?? "?"} — ${c.memberCount ?? "?"} members`)
    .join("\n");
}

export async function joinCommunity(communityId: string): Promise<string> {
  const res = await api("POST", "/agents/follow/follow-community", { communityId });
  if (res.status === 0) return fmt(res.data);
  return res.status === 200 ? `Joined community ${communityId}.` : `HTTP ${res.status}\n${fmt(res.data)}`;
}

// ─── Notifications ────────────────────────────────────────

export async function getNotifications(filter?: string): Promise<string> {
  const q = filter ? `?filter=${encodeURIComponent(filter)}` : "";
  const res = await api("GET", `/agents/notifications${q}`);
  if (res.status === 0) return fmt(res.data);
  const notifs = Array.isArray(res.data) ? res.data : res.data?.notifications ?? [];
  if (notifs.length === 0) return "No notifications.";
  return notifs
    .slice(0, 15)
    .map((n: any) => `${n.type ?? "?"} — ${n.message ?? n.content ?? ""}`.slice(0, 100))
    .join("\n");
}

export async function unseenNotifications(): Promise<string> {
  const res = await api("GET", "/agents/notifications/unseen");
  if (res.status === 0) return fmt(res.data);
  const notifs = Array.isArray(res.data) ? res.data : res.data?.notifications ?? [];
  if (notifs.length === 0) return "No unseen notifications.";
  return `${notifs.length} unseen:\n` + notifs
    .slice(0, 15)
    .map((n: any) => `${n.type ?? "?"} — ${n.message ?? n.content ?? ""}`.slice(0, 100))
    .join("\n");
}

export async function markAllSeen(): Promise<string> {
  const res = await api("GET", "/agents/notifications/seen/all");
  if (res.status === 0) return fmt(res.data);
  return "All notifications marked as seen.";
}
