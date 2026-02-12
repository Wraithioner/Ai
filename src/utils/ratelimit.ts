/** Rate limiting — prevent command spam. */

import { config } from "./config.js";

interface RateEntry {
  count: number;
  resetAt: number;
}

const limits = new Map<number, RateEntry>();
const WINDOW_MS = 60_000;

export function checkRateLimit(userId: number): { allowed: boolean; remaining: number } {
  const now = Date.now();
  let entry = limits.get(userId);

  if (!entry || now >= entry.resetAt) {
    entry = { count: 0, resetAt: now + WINDOW_MS };
    limits.set(userId, entry);
  }

  entry.count++;

  if (entry.count > config.rateLimit) {
    const waitSec = Math.ceil((entry.resetAt - now) / 1000);
    return { allowed: false, remaining: waitSec };
  }

  return { allowed: true, remaining: config.rateLimit - entry.count };
}

// Cleanup old entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of limits) {
    if (now >= entry.resetAt) limits.delete(key);
  }
}, 300_000);
