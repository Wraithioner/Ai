/** Cron/recurring tasks — persistent scheduled jobs. */

import fs from "fs";
import path from "path";
import {
  DATA_DIR,
  MIN_REMINDER_MIN,
  MAX_REMINDER_MIN,
  CRON_INTERVAL,
} from "../utils/constants.js";

const CRON_FILE = path.join(DATA_DIR, "cron.json");

interface CronJob {
  id: number;
  command: string;
  intervalMin: number;
  lastRun: string;
  nextRun: string;
  enabled: boolean;
  created: string;
}

type CronCallback = (command: string) => Promise<void>;
let callback: CronCallback | null = null;
let interval: ReturnType<typeof setInterval> | null = null;

function load(): CronJob[] {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    if (!fs.existsSync(CRON_FILE)) return [];
    return JSON.parse(fs.readFileSync(CRON_FILE, "utf-8"));
  } catch { return []; }
}

function save(jobs: CronJob[]) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(CRON_FILE, JSON.stringify(jobs, null, 2));
}

export function addCron(intervalMin: number, command: string): string {
  if (intervalMin < MIN_REMINDER_MIN || intervalMin > MAX_REMINDER_MIN) {
    return `Interval must be ${MIN_REMINDER_MIN}min to 7 days.`;
  }

  const jobs = load();
  const id = (jobs[jobs.length - 1]?.id ?? 0) + 1;
  const now = new Date();
  const next = new Date(now.getTime() + intervalMin * 60_000);

  jobs.push({
    id,
    command,
    intervalMin,
    lastRun: "",
    nextRun: next.toISOString(),
    enabled: true,
    created: now.toISOString(),
  });
  save(jobs);

  const timeStr = intervalMin >= 60
    ? `${Math.floor(intervalMin / 60)}h ${intervalMin % 60}m`
    : `${intervalMin}m`;

  return `Cron #${id} created — runs \`${command}\` every ${timeStr}.\nNext run: ${next.toLocaleString()}`;
}

export function listCrons(): string {
  const jobs = load().filter((j) => j.enabled);
  if (jobs.length === 0) return "No active cron jobs.";
  return jobs.map((j) => {
    const next = new Date(j.nextRun).toLocaleString();
    return `#${j.id} — \`${j.command}\` every ${j.intervalMin}m\nNext: ${next}`;
  }).join("\n\n");
}

export function removeCron(id: string): string {
  const rid = parseInt(id, 10);
  if (isNaN(rid)) return "Invalid cron ID.";
  const jobs = load();
  const job = jobs.find((j) => j.id === rid);
  if (!job) return `Cron #${rid} not found.`;
  job.enabled = false;
  save(jobs);
  return `Cron #${rid} disabled.`;
}

export function registerCronCallback(cb: CronCallback) {
  callback = cb;
}

export function startCronScheduler() {
  if (interval) return;
  interval = setInterval(async () => {
    const jobs = load();
    const now = Date.now();
    let changed = false;

    for (const job of jobs) {
      if (!job.enabled) continue;
      if (now >= new Date(job.nextRun).getTime()) {
        job.lastRun = new Date().toISOString();
        job.nextRun = new Date(now + job.intervalMin * 60_000).toISOString();
        changed = true;

        if (callback) {
          try { await callback(job.command); }
          catch (e) { console.error(`Cron #${job.id} failed:`, e); }
        }
      }
    }
    if (changed) save(jobs);
  }, CRON_INTERVAL);
}

export function stopCronScheduler() {
  if (interval) { clearInterval(interval); interval = null; }
}
