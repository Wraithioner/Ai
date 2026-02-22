/** Reminder scheduler — persistent reminders with background checking. */

import fs from "fs";
import path from "path";
import {
  DATA_DIR,
  MIN_REMINDER_MIN,
  MAX_REMINDER_MIN,
  SCHEDULER_INTERVAL,
} from "../utils/constants.js";

const REMINDERS_FILE = path.join(DATA_DIR, "reminders.json");

interface Reminder {
  id: number;
  message: string;
  triggerAt: string;
  created: string;
  fired: boolean;
}

type ReminderCallback = (message: string) => Promise<void>;
let callback: ReminderCallback | null = null;
let interval: ReturnType<typeof setInterval> | null = null;

function load(): Reminder[] {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    if (!fs.existsSync(REMINDERS_FILE)) return [];
    return JSON.parse(fs.readFileSync(REMINDERS_FILE, "utf-8"));
  } catch {
    return [];
  }
}

function save(reminders: Reminder[]) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(REMINDERS_FILE, JSON.stringify(reminders, null, 2));
}

export function setReminder(minutes: number, message: string): string {
  if (minutes < MIN_REMINDER_MIN || minutes > MAX_REMINDER_MIN) {
    return `Must be between ${MIN_REMINDER_MIN} min and 7 days.`;
  }

  const reminders = load();
  const id = (reminders[reminders.length - 1]?.id ?? 0) + 1;
  const triggerAt = new Date(Date.now() + minutes * 60_000);

  reminders.push({
    id,
    message,
    triggerAt: triggerAt.toISOString(),
    created: new Date().toISOString(),
    fired: false,
  });
  save(reminders);

  const timeStr =
    minutes >= 60
      ? `${Math.floor(minutes / 60)}h ${minutes % 60}m`
      : `${minutes}m`;

  return `Reminder #${id} set for ${timeStr} from now.\n${triggerAt.toLocaleString()}`;
}

export function listReminders(): string {
  const pending = load().filter((r) => !r.fired);
  if (pending.length === 0) return "No pending reminders.";
  return pending
    .map((r) => `#${r.id} — ${r.message}\nFires: ${new Date(r.triggerAt).toLocaleString()}`)
    .join("\n\n");
}

export function cancelReminder(id: string): string {
  const rid = parseInt(id, 10);
  if (isNaN(rid)) return "Invalid reminder ID.";
  const reminders = load();
  const r = reminders.find((r) => r.id === rid && !r.fired);
  if (!r) return `Reminder #${rid} not found or already fired.`;
  r.fired = true;
  save(reminders);
  return `Reminder #${rid} cancelled.`;
}

export function registerCallback(cb: ReminderCallback) {
  callback = cb;
}

export function startScheduler() {
  if (interval) return;
  interval = setInterval(async () => {
    const reminders = load();
    const now = Date.now();
    let changed = false;

    for (const r of reminders) {
      if (r.fired) continue;
      if (now >= new Date(r.triggerAt).getTime()) {
        r.fired = true;
        changed = true;
        if (callback) {
          try {
            await callback(r.message);
          } catch (e) {
            console.error("Reminder callback failed:", e);
          }
        }
      }
    }
    if (changed) save(reminders);
  }, SCHEDULER_INTERVAL);
}

export function stopScheduler() {
  if (interval) {
    clearInterval(interval);
    interval = null;
  }
}
