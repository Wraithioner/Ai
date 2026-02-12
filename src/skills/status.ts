/** Status dashboard — system overview at a glance. */

import os from "os";
import fs from "fs";
import { persona } from "../personality.js";
import { DATA_DIR } from "../utils/constants.js";

let commandCount = 0;
let lastCommand = "";
const startTime = Date.now();

export function trackCommand(cmd: string) {
  commandCount++;
  lastCommand = cmd;
}

export function getStatus(): string {
  const uptime = formatUptime(Date.now() - startTime);
  const mem = process.memoryUsage();
  const sysMem = os.totalmem();
  const freeMem = os.freemem();
  const cpuLoad = os.loadavg();

  let notesCount = 0;
  let remindersCount = 0;
  let cronCount = 0;
  try {
    const notesFile = `${DATA_DIR}/notes.json`;
    if (fs.existsSync(notesFile)) {
      notesCount = JSON.parse(fs.readFileSync(notesFile, "utf-8")).length;
    }
    const remFile = `${DATA_DIR}/reminders.json`;
    if (fs.existsSync(remFile)) {
      remindersCount = JSON.parse(fs.readFileSync(remFile, "utf-8"))
        .filter((r: any) => !r.fired).length;
    }
    const cronFile = `${DATA_DIR}/cron.json`;
    if (fs.existsSync(cronFile)) {
      cronCount = JSON.parse(fs.readFileSync(cronFile, "utf-8"))
        .filter((j: any) => j.enabled).length;
    }
  } catch { /* ignore */ }

  return [
    `*${persona.name} — Status Dashboard*`,
    "",
    `*Runtime*`,
    `Uptime: ${uptime}`,
    `Commands processed: ${commandCount}`,
    `Last command: ${lastCommand || "none"}`,
    "",
    `*Process*`,
    `Heap: ${mb(mem.heapUsed)} / ${mb(mem.heapTotal)}`,
    `RSS: ${mb(mem.rss)}`,
    `External: ${mb(mem.external)}`,
    "",
    `*System*`,
    `CPU Load: ${cpuLoad.map((l) => l.toFixed(2)).join(" / ")} (1/5/15m)`,
    `Memory: ${mb(sysMem - freeMem)} / ${mb(sysMem)} (${((1 - freeMem / sysMem) * 100).toFixed(1)}%)`,
    `CPUs: ${os.cpus().length}`,
    "",
    `*Data*`,
    `Notes: ${notesCount}`,
    `Pending reminders: ${remindersCount}`,
    `Active cron jobs: ${cronCount}`,
    "",
    `Node ${process.version} | ${os.type()} ${os.arch()}`,
  ].join("\n");
}

function formatUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  parts.push(`${s % 60}s`);
  return parts.join(" ");
}

function mb(bytes: number): string {
  return `${(bytes / 1048576).toFixed(1)} MB`;
}
