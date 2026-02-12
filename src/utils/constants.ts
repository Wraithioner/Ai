/** Shared constants — single source of truth for limits, timeouts, and paths. */

// ─── Timeouts (ms) ───────────────────────────────────────
export const TIMEOUT_SHELL = 30_000;
export const TIMEOUT_FETCH = 10_000;
export const TIMEOUT_DOWNLOAD = 30_000;
export const TIMEOUT_API = 15_000;
export const TIMEOUT_EVAL = 5_000;
export const TIMEOUT_DNS = 5_000;
export const TIMEOUT_PYTHON = 30_000;

// ─── Size Limits ─────────────────────────────────────────
export const MAX_FILE_READ = 50_000;        // 50 KB
export const MAX_FILE_UPLOAD = 50 * 1024 * 1024; // 50 MB (Telegram limit)
export const MAX_RESPONSE = 4_000;          // chars returned to user
export const MAX_FETCH_BODY = 10_000;       // HTML fetch body cap
export const MAX_API_RESPONSE = 5_000;      // API call response cap
export const MAX_ARENA_RESPONSE = 10_000;   // Arena API body cap
export const MAX_TELEGRAM_MSG = 4096;       // Telegram message cap

// ─── Depth / Count Limits ────────────────────────────────
export const MAX_SEARCH_DEPTH = 5;
export const MAX_SEARCH_RESULTS = 50;
export const MAX_GREP_RESULTS = 30;
export const MAX_GREP_FILE_SIZE = 500_000;
export const MAX_HISTORY = 50;
export const MAX_LIST_ITEMS = 20;

// ─── Scheduler ───────────────────────────────────────────
export const MIN_REMINDER_MIN = 1;
export const MAX_REMINDER_MIN = 10_080;     // 7 days
export const SCHEDULER_INTERVAL = 15_000;   // 15s check cycle
export const CRON_INTERVAL = 30_000;        // 30s check cycle

// ─── Paths ───────────────────────────────────────────────
export const DATA_DIR = process.env.DATA_DIR ?? "/app/data";
export const WORKSPACE = process.env.WORKSPACE ?? "/app";
export const DOWNLOAD_DIR = process.env.DOWNLOAD_DIR ?? "/app/data/downloads";
export const UPLOAD_DIR = process.env.UPLOAD_DIR ?? "/app/data/uploads";
export const REPOS_DIR = process.env.REPOS_DIR ?? "/app/data/repos";

// ─── User Agent ──────────────────────────────────────────
export const USER_AGENT = "Atlas/0.2";
