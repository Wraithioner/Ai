/** System skills — shell execution, sysinfo, processes. */

import { exec } from "child_process";
import os from "os";
import { shellEscape } from "../utils/sanitize.js";

export function runCommand(command: string, timeout = 30_000): Promise<string> {
  return new Promise((resolve) => {
    exec(command, { timeout }, (error, stdout, stderr) => {
      if (error?.killed) {
        resolve(`Command timed out after ${timeout / 1000}s`);
        return;
      }
      const out = stdout.trim();
      const err = stderr.trim();
      if (out && err) resolve(`${out}\n[stderr] ${err}`);
      else if (err) resolve(`[stderr] ${err}`);
      else if (out) resolve(out);
      else resolve(`Exit code: ${error?.code ?? 0}`);
    });
  });
}

export function sysInfo(): string {
  const uptime = os.uptime();
  const days = Math.floor(uptime / 86400);
  const hours = Math.floor((uptime % 86400) / 3600);
  const mins = Math.floor((uptime % 3600) / 60);

  const mem = os.totalmem();
  const free = os.freemem();
  const usedPct = (((mem - free) / mem) * 100).toFixed(1);

  return [
    `OS: ${os.type()} ${os.release()}`,
    `Arch: ${os.arch()}`,
    `CPUs: ${os.cpus().length}x ${os.cpus()[0]?.model ?? "unknown"}`,
    `Memory: ${formatBytes(mem - free)} / ${formatBytes(mem)} (${usedPct}%)`,
    `Hostname: ${os.hostname()}`,
    `Uptime: ${days}d ${hours}h ${mins}m`,
    `Node: ${process.version}`,
    `CWD: ${process.cwd()}`,
  ].join("\n");
}

export async function listProcesses(filter?: string): Promise<string> {
  const cmd = filter
    ? `ps aux | grep -i ${shellEscape(filter)} | grep -v grep | head -20`
    : "ps aux --sort=-%mem | head -20";
  return runCommand(cmd);
}

export async function killProcess(pid: string): Promise<string> {
  const n = parseInt(pid, 10);
  if (isNaN(n)) return "Invalid PID.";
  try {
    process.kill(n, "SIGKILL");
    return `Killed process ${n}`;
  } catch (e: any) {
    return `Failed: ${e.message}`;
  }
}

let startTime = Date.now();
export function botUptime(): string {
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const d = Math.floor(elapsed / 86400);
  const h = Math.floor((elapsed % 86400) / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  const s = elapsed % 60;
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return `Bot uptime: ${parts.join(" ")}`;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}
